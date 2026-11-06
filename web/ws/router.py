import uuid

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from application.errors import AuthenticationError, ForbiddenError, NotFoundError
from application.jwt_service import JWTService
from application.use_cases import GetGameSessionUseCase
from di.composition import AppContext, get_context, get_jwt_service
from infrastructure.repositories.game_session import GameSessionRepository
from web.mapper import WebGameMapper
from web.ws.manager import notifier

ws_router = APIRouter(prefix="/game", tags=["WebSocket"])


@ws_router.websocket("/{game_session_id}/ws")
async def game_websocket_endpoint(
    websocket: WebSocket,
    context: AppContext = Depends(get_context),
    game_session_id: uuid.UUID = Path(...),
    token: str = Query(...),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """
    Подписка на обновления игры.

    Сессию БД открываем только на время чтения состояния: время жизни
    зависимости FastAPI здесь равно времени жизни соединения, и обычный
    Depends(get_db_session) держал бы транзакцию до отключения клиента.
    """
    session_id_str = str(game_session_id)

    try:
        player_id = jwt_service.decode_access_token(token)
    except AuthenticationError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with context.session_factory() as session:
        use_case = GetGameSessionUseCase(
            game_session_repository=GameSessionRepository(session)
        )
        try:
            game_session = await use_case.execute(
                game_session_id=session_id_str, player_id=player_id
            )
        except (NotFoundError, ForbiddenError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await notifier.connect(game_session_id=session_id_str, websocket=websocket)

    try:
        await websocket.send_json(
            WebGameMapper.to_web_response(game_session).model_dump(mode="json")
        )

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        notifier.disconnect(game_session_id=session_id_str, websocket=websocket)
