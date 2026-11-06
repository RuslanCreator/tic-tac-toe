import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from domain.errors import DomainError

from .playing_board import CellState, PlayingBoard


class GameRules:
    @staticmethod
    def get_winner(board: PlayingBoard) -> CellState:
        for line in board.iter_lines():
            if len(line) != board.grid_size:
                continue

            first_cell = line[0]
            if first_cell != CellState.EMPTY and all(
                cell == first_cell for cell in line
            ):
                return first_cell

        return CellState.EMPTY


class GameSessionState(str, Enum):
    WAITING = "WAITING"
    TURN_X = "TURN_X"
    TURN_O = "TURN_O"
    DRAW = "DRAW"
    WON_X = "WON_X"
    WON_O = "WON_O"


@dataclass(kw_only=True)
class GameSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    board: PlayingBoard = field(default_factory=lambda: PlayingBoard.create_empty())
    player_x_id: str | None = None
    player_o_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _status: GameSessionState = GameSessionState.WAITING

    @property
    def status(self) -> GameSessionState:
        return self._status

    @property
    def status_text(self) -> str:
        match self._status:
            case GameSessionState.WAITING:
                return "Waiting for players"
            case GameSessionState.DRAW:
                return "Draw"
            case GameSessionState.TURN_X:
                return f"Player’s turn with UUID {self.player_x_id}"
            case GameSessionState.TURN_O:
                return f"Player’s turn with UUID {self.player_o_id}"
            case GameSessionState.WON_X:
                return f"Victory for player with UUID {self.player_x_id}"
            case GameSessionState.WON_O:
                return f"Victory for player with UUID {self.player_o_id}"
            case _:
                return "Waiting for players"

    @classmethod
    def restore(
        cls,
        id: str,
        board: PlayingBoard,
        player_x_id: str | None,
        player_o_id: str | None,
        status: GameSessionState,
        created_at: datetime | None = None,
    ) -> "GameSession":
        session = cls(
            id=id,
            board=board,
            player_x_id=player_x_id,
            player_o_id=player_o_id,
            created_at=created_at or datetime.now(timezone.utc),
        )
        session._status = status
        return session

    def get_current_player_id(self) -> str:
        if self._status == GameSessionState.TURN_O:
            return self.player_o_id
        elif self._status == GameSessionState.TURN_X:
            return self.player_x_id
        raise DomainError("Игроки еще не подключились!")

    def get_current_turn_sign(self) -> CellState:
        if self._status == GameSessionState.TURN_O:
            return CellState.SIGN_O
        return CellState.SIGN_X

    def setup_match(self, player_id_o: str) -> None:
        if self._status != GameSessionState.WAITING:
            raise DomainError(
                "Невозможно запустить матч: сессия уже активна или завершена!"
            )

        if not self.player_x_id:
            raise DomainError("Ошибка домена: у лобби отсутствует создатель (игрок X)!")

        if self.player_o_id is not None:
            raise DomainError("В этой игровой сессии уже нет свободных мест!")

        self.player_o_id = player_id_o
        self._status = GameSessionState.TURN_X

    def make_move(self, row: int, col: int, player_id: str) -> None:
        if self._status == GameSessionState.WAITING:
            raise DomainError("Нельзя совершить ход! Игра ожидает второго игрока.")
        if self.is_finished():
            raise DomainError("Попытка сделать ход в уже завершенной игре!")

        expected_player_id = self.get_current_player_id()
        if player_id != expected_player_id:
            raise DomainError("Сейчас ход другого игрока!")

        self.board = self.board.set_cell(row, col, self.get_current_turn_sign())
        winner = GameRules.get_winner(self.board)

        if winner == CellState.SIGN_X:
            self._status = GameSessionState.WON_X
        elif winner == CellState.SIGN_O:
            self._status = GameSessionState.WON_O
        elif self.board.is_full():
            self._status = GameSessionState.DRAW
        else:
            self._status = (
                GameSessionState.TURN_O
                if self._status == GameSessionState.TURN_X
                else GameSessionState.TURN_X
            )

    def is_finished(self) -> bool:
        return self._status in (
            GameSessionState.DRAW,
            GameSessionState.WON_X,
            GameSessionState.WON_O,
        )

    def is_participant(self, player_id: str) -> bool:
        return player_id in (self.player_x_id, self.player_o_id)
