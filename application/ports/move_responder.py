from typing import Protocol

from domain.entities.game_session import GameSession


class MoveResponder(Protocol):
    """Действие, которое выполняется сразу после хода человека."""

    def respond(self, session: GameSession) -> None: ...
