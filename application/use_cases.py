from application.services import MiniMaxService, PasswordCryptoService
from domain.entities.game_session import (
    GameSession,
    GameSessionState,
    WaitingSessionInfo,
)
from domain.entities.player import Player
from domain.interfaces import (
    GameSessionRepositoryInterface,
    PlayerRepositoryInterface,
)


class SignUpUseCase:
    def __init__(
        self,
        player_repository: PlayerRepositoryInterface,
        crypto_service: PasswordCryptoService,
    ):
        self._player_repository = player_repository
        self._crypto_service = crypto_service

    async def execute(self, login: str, password: str) -> str:
        existing = await self._player_repository.get_by_login(login)
        if existing:
            raise ValueError(f"Игрок с логином {login} уже существует!")

        new_player = Player(login=login)
        password_hash = self._crypto_service.hash_password(password)

        await self._player_repository.save(new_player, password_hash)
        return new_player.id


class AuthenticatePlayerUseCase:
    def __init__(
        self,
        player_repository: PlayerRepositoryInterface,
        crypto_service: PasswordCryptoService,
    ):
        self._player_repository = player_repository
        self._crypto_service = crypto_service

    async def execute(self, login: str, password: str) -> str:
        player_data = await self._player_repository.get_by_login(login)
        if not player_data:
            raise ValueError("Кто ты, воин?")

        player, stored_hash = player_data

        if stored_hash != self._crypto_service.hash_password(password):
            raise ValueError("Неверный логин или пароль")

        return player.id


class CreatePvEGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, player_id: str) -> GameSession:
        new_game_session = GameSession(
            player_x_id=player_id, player_o_id="bot", _status=GameSessionState.TURN_X
        )
        await self._game_session_repository.add(new_game_session)

        return new_game_session


class CreatePvPGameUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, player_id: str) -> GameSession:
        new_game_session = GameSession(
            player_x_id=player_id, player_o_id=None, _status=GameSessionState.WAITING
        )
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
            raise ValueError(f"Игровая сессия с ID {game_session_id} не найдена!")

        if player_id in (game_session.player_x_id, game_session.player_o_id):
            return game_session

        game_session.setup_match(player_id_o=player_id)

        await self._game_session_repository.update(game_session)
        return game_session


class MakeMovePvPUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

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
            raise ValueError(f"Игровая сессия с ID {game_session_id} не найдена!")

        game_session.make_move(row, col, player_id)
        await self._game_session_repository.update(game_session)

        return game_session


class MakeMovePvEUseCase:
    def __init__(
        self,
        game_session_repository: GameSessionRepositoryInterface,
        ai_engine: MiniMaxService,
    ):
        self._game_session_repository = game_session_repository
        self._ai_engine = ai_engine

    async def execute(
        self,
        game_session_id: str,
        row: int,
        col: int,
        player_id: str,
    ) -> GameSession:
        game_session = await self._game_session_repository.get_by_id(game_session_id)
        if not game_session:
            raise ValueError(f"Игровая сессия с ID {game_session_id} не найдена!")

        game_session.make_move(row, col, player_id)

        if not game_session.is_finished():
            ai_row, ai_col = self._ai_engine.calculate_best_move(
                board=game_session.board, ai_sign=game_session.get_current_turn_sign()
            )
            game_session.make_move(ai_row, ai_col, "bot")

        await self._game_session_repository.update(game_session)
        return game_session


class DeleteGameSessionUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self.game_session_repository = game_session_repository

    async def execute(self, game_session_id: str, player_id: str) -> None:
        session = await self.game_session_repository.get_by_id(game_session_id)
        if not session:
            raise ValueError("Игровая сессия не найдена")

        if session.player_x_id != player_id:
            raise ValueError("Только создатель лобби может удалить его")

        if session.status in {
            GameSessionState.WON_X,
            GameSessionState.WON_O,
            GameSessionState.DRAW,
        }:
            raise ValueError("Нельзя удалить уже начатую игру")

        await self.game_session_repository.delete(game_session_id)


class GetWaitingSessionsUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self) -> list[WaitingSessionInfo]:
        return await self._game_session_repository.get_waiting_sessions()


class GetGameSessionUseCase:
    def __init__(self, game_session_repository: GameSessionRepositoryInterface):
        self._game_session_repository = game_session_repository

    async def execute(self, game_session_id: str) -> GameSession:
        game_session = await self._game_session_repository.get_by_id(game_session_id)
        if not game_session:
            raise ValueError(f"Игровая сессия с ID {game_session_id} не найдена")
        return game_session


class GetPlayerByUuidUseCase:
    def __init__(self, player_repository: PlayerRepositoryInterface):
        self._player_repository = player_repository

    async def execute(self, player_id: str) -> Player:
        player = await self._player_repository.get_by_id(player_id)
        if not player:
            raise ValueError(f"Пользователь с UUID {player_id} не найден")
        return player
