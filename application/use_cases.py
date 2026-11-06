from application.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from application.ports.password_hasher import PasswordHasherInterface
from application.ports.repositories import (
    GameSessionRepositoryInterface,
    PlayerRepositoryInterface,
)
from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from application.strategies import MoveResponderRegistry
from domain.entities.game_session import GameSession, GameSessionState
from domain.entities.player import Player


class SignUpUseCase:
    def __init__(
        self,
        player_repository: PlayerRepositoryInterface,
        crypto_service: PasswordHasherInterface,
    ):
        self._player_repository = player_repository
        self._crypto_service = crypto_service

    async def execute(self, login: str, password: str) -> str:
        existing = await self._player_repository.get_by_login(login)
        if existing:
            raise ConflictError(f"Игрок с логином {login} уже существует!")

        new_player = Player(login=login)
        password_hash = self._crypto_service.hash_password(password)

        await self._player_repository.save(new_player, password_hash)
        return new_player.id


class AuthenticatePlayerUseCase:
    def __init__(
        self,
        player_repository: PlayerRepositoryInterface,
        crypto_service: PasswordHasherInterface,
    ):
        self._player_repository = player_repository
        self._crypto_service = crypto_service

    async def execute(self, login: str, password: str) -> Player:
        player_data = await self._player_repository.get_by_login(login)
        if not player_data:
            raise AuthenticationError("Неверный логин или пароль")

        player, stored_hash = player_data

        if not self._crypto_service.verify_password(password, stored_hash):
            raise AuthenticationError("Неверный логин или пароль")

        return player


class CreatePvEGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, player_id: str) -> GameSession:
        new_game_session = GameSession.create_pve(player_id)
        await self._game_session_repository.add(new_game_session)

        return new_game_session


class CreatePvPGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, player_id: str) -> GameSession:
        new_game_session = GameSession.create_pvp(player_id)
        await self._game_session_repository.add(new_game_session)

        return new_game_session


class JoinPvPGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, game_session_id: str, player_id: str) -> GameSession:
        game_session = await self._game_session_repository.get_by_id_for_update(
            game_session_id
        )
        if not game_session:
            raise NotFoundError(f"Игровая сессия с ID {game_session_id} не найдена!")

        if game_session.is_pve:
            raise ConflictError("Нельзя присоединиться к игре с ботом")

        if player_id in (game_session.player_x_id, game_session.player_o_id):
            return game_session

        if game_session.status != GameSessionState.WAITING:
            raise ConflictError("В этой игре уже нет свободных мест")

        game_session.setup_match(player_id_o=player_id)

        await self._game_session_repository.update(game_session)
        return game_session


class MakeMoveUseCase:
    def __init__(
        self,
        game_session_repository: GameSessionRepositoryInterface,
        responders: MoveResponderRegistry,
    ):
        self._game_session_repository = game_session_repository
        self._responders = responders

    async def execute(
        self,
        game_session_id: str,
        row: int,
        col: int,
        player_id: str,
    ) -> GameSession:
        game_session = await self._game_session_repository.get_by_id_for_update(
            game_session_id
        )
        if not game_session:
            raise NotFoundError(f"Игровая сессия с ID {game_session_id} не найдена!")

        if not game_session.is_participant(player_id):
            raise ForbiddenError("Нет доступа к этой игре")

        game_session.make_move(row, col, player_id)
        self._responders.get(game_session.mode).respond(game_session)

        await self._game_session_repository.update(game_session)
        return game_session


class LeaveGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(
        self,
        game_session_id: str,
        player_id: str,
    ) -> GameSession | None:
        """
        Возвращает:
        - None, если игра удалена (лобби или PvE);
        - GameSession, если игрок сдался или игра уже завершена.
        """
        game_session = await self._game_session_repository.get_by_id_for_update(
            game_session_id
        )
        if not game_session:
            raise NotFoundError("Игровая сессия не найдена")

        if not game_session.is_participant(player_id):
            raise ForbiddenError("Нет доступа к этой игре")

        if game_session.is_finished():
            return game_session

        if game_session.is_waiting or game_session.is_pve:
            await self._game_session_repository.delete(game_session_id)
            return None

        game_session.resign(player_id)
        await self._game_session_repository.update(game_session)
        return game_session


class GetWaitingSessionsUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self) -> list[WaitingSessionInfo]:
        return await self._game_session_repository.get_waiting_sessions()


class GetGameSessionUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, game_session_id: str, player_id: str) -> GameSession:
        game_session = await self._game_session_repository.get_by_id(game_session_id)
        if not game_session:
            raise NotFoundError(f"Игровая сессия с ID {game_session_id} не найдена")

        if not game_session.is_participant(player_id):
            raise ForbiddenError("Нет доступа к этой игре")

        return game_session


class GetPlayerByUuidUseCase:
    def __init__(self, player_repository: PlayerRepositoryInterface):
        self._player_repository = player_repository

    async def execute(self, player_id: str) -> Player:
        player = await self._player_repository.get_by_id(player_id)
        if not player:
            raise NotFoundError(f"Пользователь с UUID {player_id} не найден")
        return player


class GetFinishedSessionsUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, player_id: str) -> list[FinishedSessionInfo]:
        return await self._game_session_repository.get_finished_by_player_id(player_id)
