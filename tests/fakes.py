import copy
from typing import Literal

from application.errors import ConflictError, NotFoundError
from application.jwt_service import JWTService
from application.ports.ai_player import AIPlayerInterface
from application.ports.password_hasher import PasswordHasherInterface
from application.ports.repositories import (
    GameSessionRepositoryInterface,
    PlayerRepositoryInterface,
)
from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from domain.entities.game_session import GameSession, GameSessionState
from domain.entities.player import Player
from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError


class FakePasswordHasher(PasswordHasherInterface):
    def hash_password(self, password: str) -> str:
        return f"hashed::{password}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed::{password}"


class FakeAIPlayer(AIPlayerInterface):
    def __init__(
        self,
        move: tuple[int, int] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._move = move
        self._error = error
        self.calls: list[tuple[PlayingBoard, CellState]] = []

    def calculate_best_move(
        self, board: PlayingBoard, ai_sign: CellState
    ) -> tuple[int, int]:
        self.calls.append((board, ai_sign))
        if self._error is not None:
            raise self._error

        if self._move is not None:
            return self._move

        empty_cells = board.get_empty_cells()
        if not empty_cells:
            raise DomainError("Нет доступных клеток для хода ИИ!")
        return empty_cells[0]


class InMemoryPlayerRepository(PlayerRepositoryInterface):
    def __init__(self) -> None:
        self.players: dict[str, Player] = {}
        self.password_hashes: dict[str, str] = {}
        self.player_ids_by_login: dict[str, str] = {}

    async def save(self, player: Player, password_hash: str) -> None:
        if player.login in self.player_ids_by_login:
            raise ConflictError("Игрок с таким логином уже существует")
        if player.id in self.players:
            raise ConflictError("Игрок с таким ID уже существует")

        self.players[player.id] = player
        self.password_hashes[player.id] = password_hash
        self.player_ids_by_login[player.login] = player.id

    async def get_by_login(self, login: str) -> tuple[Player, str] | None:
        player_id = self.player_ids_by_login.get(login)
        if player_id is None:
            return None
        return self.players[player_id], self.password_hashes[player_id]

    async def get_by_id(self, player_id: str) -> Player | None:
        return self.players.get(player_id)


class InMemoryGameSessionRepository(GameSessionRepositoryInterface):
    def __init__(
        self,
        player_logins: dict[str, str] | None = None,
        player_repository: InMemoryPlayerRepository | None = None,
    ) -> None:
        self.sessions: dict[str, GameSession] = {}
        self.player_logins = player_logins or {}
        self.player_repository = player_repository
        self.for_update_calls = 0

    async def get_by_id(self, game_session_id: str) -> GameSession | None:
        session = self.sessions.get(game_session_id)
        return copy.deepcopy(session) if session is not None else None

    async def get_by_id_for_update(self, game_session_id: str) -> GameSession | None:
        self.for_update_calls += 1
        return await self.get_by_id(game_session_id)

    async def add(self, game_session: GameSession) -> None:
        self.sessions[game_session.id] = copy.deepcopy(game_session)

    async def update(self, game_session: GameSession) -> None:
        if game_session.id not in self.sessions:
            raise NotFoundError(f"Игровая сессия {game_session.id} не найдена")
        self.sessions[game_session.id] = copy.deepcopy(game_session)

    async def get_waiting_sessions(self) -> list[WaitingSessionInfo]:
        result: list[WaitingSessionInfo] = []
        for session in self.sessions.values():
            if session.status != GameSessionState.WAITING:
                continue

            creator_id = session.player_x_id or ""
            creator_login = self.player_logins.get(creator_id)
            if creator_login is None and self.player_repository is not None:
                player = self.player_repository.players.get(creator_id)
                creator_login = player.login if player is not None else creator_id
            if creator_login is None:
                creator_login = creator_id

            result.append(
                WaitingSessionInfo(
                    game_session_id=session.id,
                    creator_login=creator_login,
                )
            )
        return result

    async def delete(self, game_session_id: str) -> None:
        self.sessions.pop(game_session_id, None)

    async def get_finished_by_player_id(
        self, player_id: str
    ) -> list[FinishedSessionInfo]:
        result: list[FinishedSessionInfo] = []
        for session in self.sessions.values():
            if not session.is_finished():
                continue
            if player_id not in (session.player_x_id, session.player_o_id):
                continue

            result.append(
                FinishedSessionInfo(
                    game_session_id=session.id,
                    status=session.status,
                    result=self._result_for(session, player_id),
                    created_at=session.created_at,
                )
            )

        return sorted(result, key=lambda info: info.created_at, reverse=True)

    @staticmethod
    def _result_for(
        session: GameSession, player_id: str
    ) -> Literal["WIN", "DRAW", "LOSE"]:
        if session.status == GameSessionState.DRAW:
            return "DRAW"
        if (
            session.status == GameSessionState.WON_X
            and session.player_x_id == player_id
        ) or (
            session.status == GameSessionState.WON_O
            and session.player_o_id == player_id
        ):
            return "WIN"
        return "LOSE"


class FakeConnection:
    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def execute(self, statement: object) -> None:
        if not self._healthy:
            raise RuntimeError("database is down")


class FakeEngine:
    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def connect(self) -> FakeConnection:
        return FakeConnection(self._healthy)


class FakeAppContext:
    def __init__(
        self,
        jwt_service: JWTService,
        crypto_service: PasswordHasherInterface | None = None,
        ai_engine: AIPlayerInterface | None = None,
        *,
        healthy: bool = True,
    ) -> None:
        self.jwt_service = jwt_service
        self.crypto_service = crypto_service or FakePasswordHasher()
        self.ai_engine = ai_engine or FakeAIPlayer()
        self.engine = FakeEngine(healthy)
        self.session_factory = None

    async def dispose(self) -> None:
        pass
