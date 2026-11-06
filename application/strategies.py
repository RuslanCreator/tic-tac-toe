from collections.abc import Mapping

from application.ports.ai_player import AIPlayerInterface
from application.ports.move_responder import MoveResponder
from domain.entities.game_session import GameMode, GameSession
from domain.entities.player import BOT_PLAYER_ID


class PvpMoveResponder:
    """В PvP после хода человека ничего не происходит."""

    def respond(self, session: GameSession) -> None:
        pass


class PveMoveResponder:
    """В PvE после хода человека отвечает бот."""

    def __init__(self, ai_engine: AIPlayerInterface) -> None:
        self._ai_engine = ai_engine

    def respond(self, session: GameSession) -> None:
        if session.is_finished():
            return

        row, col = self._ai_engine.calculate_best_move(
            board=session.board,
            ai_sign=session.get_current_turn_sign(),
        )
        session.make_move(row, col, BOT_PLAYER_ID)


class MoveResponderRegistry:
    """Выбирает стратегию ответа по режиму конкретной игры."""

    def __init__(self, responders: Mapping[GameMode, MoveResponder]) -> None:
        missing = set(GameMode) - set(responders)
        if missing:
            modes = ", ".join(mode.value for mode in missing)
            raise ValueError(f"Нет стратегии ответа для режимов: {modes}")

        self._responders = dict(responders)

    def get(self, mode: GameMode) -> MoveResponder:
        return self._responders[mode]
