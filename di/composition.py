import uuid
from collections.abc import AsyncGenerator

from fastapi import (
    Depends,
    Path,
    Query,
    WebSocket,
    WebSocketException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import HTTPConnection

from application.errors import AuthenticationError, ForbiddenError, NotFoundError
from application.jwt_service import JWTService
from application.ports.ai_player import AIPlayerInterface
from application.ports.password_hasher import PasswordHasherInterface
from application.services import MiniMaxService, PasswordCryptoService
from application.strategies import (
    MoveResponderRegistry,
    PveMoveResponder,
    PvpMoveResponder,
)
from application.use_cases import (
    AuthenticatePlayerUseCase,
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    GetFinishedSessionsUseCase,
    GetGameSessionUseCase,
    GetPlayerByUuidUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    LeaveGameUseCase,
    MakeMoveUseCase,
    SignUpUseCase,
)
from di.settings import Settings
from domain.entities.game_session import GameMode, GameSession
from infrastructure.repositories.game_session import GameSessionRepository
from infrastructure.repositories.player import PlayerRepository

WS_TOKEN_PROTOCOL = "access_token"


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
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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


def get_move_responders(
    context: AppContext = Depends(get_context),
) -> MoveResponderRegistry:
    return MoveResponderRegistry(
        {
            GameMode.PVP: PvpMoveResponder(),
            GameMode.PVE: PveMoveResponder(context.ai_engine),
        }
    )


def get_make_move_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
    responders: MoveResponderRegistry = Depends(get_move_responders),
) -> MakeMoveUseCase:
    return MakeMoveUseCase(
        game_session_repository=repository,
        responders=responders,
    )


def get_create_pvp_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> CreatePvPGameUseCase:
    return CreatePvPGameUseCase(game_session_repository=repository)


def get_join_pvp_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> JoinPvPGameUseCase:
    return JoinPvPGameUseCase(game_session_repository=repository)


def get_waiting_session_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> GetWaitingSessionsUseCase:
    return GetWaitingSessionsUseCase(game_session_repository=repository)


def get_leave_game_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
) -> LeaveGameUseCase:
    return LeaveGameUseCase(game_session_repository=repository)


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


def _extract_ws_token(websocket: WebSocket, query_token: str | None) -> str:
    """Берёт токен из Sec-WebSocket-Protocol, а query-параметр оставляет
    как совместимый fallback для старых клиентов."""
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    for protocol in protocols.split(","):
        protocol = protocol.strip()
        if protocol and protocol != WS_TOKEN_PROTOCOL:
            return protocol

    if query_token:
        return query_token

    raise AuthenticationError("Не передан токен для WebSocket-соединения")


async def get_ws_player_id(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> str:
    try:
        raw_token = _extract_ws_token(websocket, token)
        return jwt_service.decode_access_token(raw_token)
    except AuthenticationError as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc


async def get_ws_game_session(
    game_session_id: uuid.UUID = Path(...),
    player_id: str = Depends(get_ws_player_id),
    context: AppContext = Depends(get_context),
) -> GameSession:
    """Загружает и авторизует игру до accept(), не удерживая сессию БД."""
    async with context.session_factory() as session:
        use_case = GetGameSessionUseCase(
            game_session_repository=GameSessionRepository(session)
        )
        try:
            return await use_case.execute(
                game_session_id=str(game_session_id), player_id=player_id
            )
        except (NotFoundError, ForbiddenError) as exc:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc
