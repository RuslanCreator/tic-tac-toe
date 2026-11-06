from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import HTTPConnection

from application.jwt_service import JWTService
from application.ports.ai_player import AIPlayerInterface
from application.ports.password_hasher import PasswordHasherInterface
from application.services import MiniMaxService, PasswordCryptoService
from application.use_cases import (
    AuthenticatePlayerUseCase,
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    DeleteGameSessionUseCase,
    GetFinishedSessionsUseCase,
    GetGameSessionUseCase,
    GetPlayerByUuidUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    MakeMovePvEUseCase,
    MakeMovePvPUseCase,
    SignUpUseCase,
)
from di.settings import Settings
from infrastructure.repositories.game_session import GameSessionRepository
from infrastructure.repositories.player import PlayerRepository


class AppContext:
    """
    Composition root: создаёт и хранит долгоживущие ресурсы приложения.
    Экземпляр собирается в lifespan и живёт в app.state.
    Резолвингом зависимостей занимается FastAPI Depends, не этот класс.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jwt_service = JWTService(
            secret_key=settings.jwt.secret_key.get_secret_value(),
            algorithm=settings.jwt.algorithm,
            expire_minutes=settings.jwt.expire_minutes,
        )
        self.engine = create_async_engine(settings.database_url, echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self.crypto_service: PasswordHasherInterface = PasswordCryptoService()
        self.ai_engine: AIPlayerInterface = MiniMaxService()

    async def dispose(self) -> None:
        await self.engine.dispose()


def get_context(connection: HTTPConnection) -> AppContext:
    return connection.app.state.context


async def get_db_session(
    context: AppContext = Depends(get_context),
) -> AsyncGenerator[AsyncSession, None]:
    async with context.session_factory() as session:
        yield session


# Каждая функция принимает свежую сессию базы данных этого конкретного HTTP-запроса,
# создает временный репозиторий и запечатывает его в Use Case.


def get_player_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PlayerRepository:
    return PlayerRepository(session=session)


def get_signup_use_case(
    context: AppContext = Depends(get_context),
    repository: PlayerRepository = Depends(get_player_repository),
) -> SignUpUseCase:
    return SignUpUseCase(
        player_repository=repository,
        crypto_service=context.crypto_service,
    )


def get_authenticate_player_use_case(
    context: AppContext = Depends(get_context),
    repository: PlayerRepository = Depends(get_player_repository),
) -> AuthenticatePlayerUseCase:
    return AuthenticatePlayerUseCase(
        player_repository=repository,
        crypto_service=context.crypto_service,
    )


def get_jwt_service(
    context: AppContext = Depends(get_context),
) -> JWTService:
    return context.jwt_service


def get_game_session_repository(
    session: AsyncSession = Depends(get_db_session),
) -> GameSessionRepository:
    return GameSessionRepository(session=session)


def get_create_pve_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> CreatePvEGameUseCase:
    return CreatePvEGameUseCase(game_session_repository=repository)


def get_make_move_pve_use_case(
    context: AppContext = Depends(get_context),
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> MakeMovePvEUseCase:
    return MakeMovePvEUseCase(
        game_session_repository=repository,
        ai_engine=context.ai_engine,
    )


def get_create_pvp_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> CreatePvPGameUseCase:
    return CreatePvPGameUseCase(game_session_repository=repository)


def get_make_move_pvp_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> MakeMovePvPUseCase:
    return MakeMovePvPUseCase(game_session_repository=repository)


def get_join_pvp_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> JoinPvPGameUseCase:
    return JoinPvPGameUseCase(game_session_repository=repository)


def get_waiting_session_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> GetWaitingSessionsUseCase:
    return GetWaitingSessionsUseCase(game_session_repository=repository)


def get_delete_session_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> DeleteGameSessionUseCase:
    return DeleteGameSessionUseCase(game_session_repository=repository)


def get_game_session_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> GetGameSessionUseCase:
    return GetGameSessionUseCase(game_session_repository=repository)


def get_user_by_uuid_use_case(
    repository: PlayerRepository = Depends(get_player_repository),
) -> GetPlayerByUuidUseCase:
    return GetPlayerByUuidUseCase(player_repository=repository)


def get_finished_sessions_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> GetFinishedSessionsUseCase:
    return GetFinishedSessionsUseCase(game_session_repository=repository)
