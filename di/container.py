import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from application.services import MiniMaxService, PasswordCryptoService
from application.use_cases import (
    AuthenticatePlayerUseCase,
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    DeleteGameSessionUseCase,
    GetGameSessionUseCase,
    GetPlayerByUuidUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    MakeMovePvEUseCase,
    MakeMovePvPUseCase,
    SignUpUseCase,
)
from datasource.repositories.game_session import GameSessionRepository
from datasource.repositories.player import PlayerRepository

DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")
# Замени на свои данные от локального Postgres на Маке
# Если пароля нет, пиши просто: postgresql+asyncpg://имя_юзера@localhost:5432/tictactoe_db
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}"


class DependencyContainer:
    """
    Контейнер для долгоживущих инфраструктурных компонентов (Синглтонов).
    Создается один раз при старте веб-сервера.
    """

    def __init__(self) -> None:
        # 1. Создаем один асинхронный движок.
        # Он управляет пулом сетевых соединений с Postgres.
        self.engine = create_async_engine(DATABASE_URL, echo=False)

        # 2. Создаем фабрику (генератор),
        # которая умеет штамповать новые изолированные сессии
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )

        self._crypto_service = PasswordCryptoService()

        # 3. Мозги ИИ по-прежнему синглтон,
        # они не привязаны к сессиям базы данных
        self._ai_engine = MiniMaxService()

    @property
    def ai_engine(self) -> MiniMaxService:
        return self._ai_engine

    @property
    def crypto_service(self) -> PasswordCryptoService:
        return self._crypto_service


# Создаем один глобальный экземпляр долгоживущих настроек
infra_container = DependencyContainer()


async def get_db_session():
    """
    Асинхронный провайдер сессии.
    FastAPI автоматически откроет транзакцию в начале запроса и
    гарантированно закроет её в конце!
    """
    async with infra_container.session_factory() as session:
        async with session.begin():
            yield session


# Каждая функция принимает свежую сессию базы данных этого конкретного HTTP-запроса,
# создает временный репозиторий и запечатывает его в Use Case.


def get_player_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PlayerRepository:
    return PlayerRepository(session=session)


def get_signup_use_case(
    repository: PlayerRepository = Depends(get_player_repository),
) -> SignUpUseCase:
    return SignUpUseCase(
        player_repository=repository, crypto_service=infra_container.crypto_service
    )


def get_authenticate_player_use_case(
    repository: PlayerRepository = Depends(get_player_repository),
) -> AuthenticatePlayerUseCase:
    return AuthenticatePlayerUseCase(
        player_repository=repository, crypto_service=infra_container.crypto_service
    )


def get_game_session_repository(
    session: AsyncSession = Depends(get_db_session),
) -> GameSessionRepository:
    return GameSessionRepository(session=session)


def get_create_pve_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> CreatePvEGameUseCase:
    return CreatePvEGameUseCase(game_session_repository=repository)


def get_make_move_pve_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> MakeMovePvEUseCase:
    return MakeMovePvEUseCase(
        game_session_repository=repository, ai_engine=infra_container.ai_engine
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
