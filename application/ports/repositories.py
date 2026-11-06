from abc import ABC, abstractmethod

from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from domain.entities.game_session import GameSession
from domain.entities.player import Player


class GameSessionRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, game_session_id: str) -> GameSession | None: ...

    @abstractmethod
    async def get_by_id_for_update(
        self, game_session_id: str
    ) -> GameSession | None: ...

    @abstractmethod
    async def add(self, game_session: GameSession) -> None: ...

    @abstractmethod
    async def update(self, game_session: GameSession) -> None: ...

    @abstractmethod
    async def get_waiting_sessions(self) -> list[WaitingSessionInfo]: ...

    @abstractmethod
    async def delete(self, game_session_id: str) -> None: ...

    @abstractmethod
    async def get_finished_by_player_id(
        self, player_id: str
    ) -> list[FinishedSessionInfo]: ...


class PlayerRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, player: Player, password_hash: str) -> None: ...

    @abstractmethod
    async def get_by_login(self, login: str) -> tuple[Player, str] | None: ...

    @abstractmethod
    async def get_by_id(self, player_id: str) -> Player | None: ...
