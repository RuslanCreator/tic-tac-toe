from abc import ABC, abstractmethod

from domain.entities.game_session import GameSession, WaitingSessionInfo
from domain.entities.player import Player


class GameSessionRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, game_session_id: str) -> GameSession | None:
        pass

    @abstractmethod
    async def get_by_id_for_update(self, game_session_id: str) -> GameSession | None:
        pass

    @abstractmethod
    async def add(self, game_session: GameSession) -> None:
        pass

    @abstractmethod
    async def update(self, game_session: GameSession) -> None:
        pass

    @abstractmethod
    async def get_waiting_sessions(self) -> list[WaitingSessionInfo]:
        pass

    @abstractmethod
    async def delete(self, game_session_id: str) -> None:
        pass


class PlayerRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, player: Player, password_hash: str) -> None:
        pass

    @abstractmethod
    async def get_by_login(self, login: str) -> tuple[Player, str] | None:
        pass

    @abstractmethod
    async def get_by_id(self, player_id: str) -> Player | None:
        pass
