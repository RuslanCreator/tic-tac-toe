import uuid

from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect

from di.composition import get_ws_game_session
from domain.entities.game_session import GameSession
from web.mapper import WebGameMapper
from web.ws.manager import notifier

ws_router = APIRouter(prefix="/game", tags=["WebSocket"])


@ws_router.websocket("/{game_session_id}/ws")
async def game_websocket_endpoint(
    websocket: WebSocket,
    game_session_id: uuid.UUID = Path(...),
    game_session: GameSession = Depends(get_ws_game_session),
):
    """
    Подписка на обновления игры.

    Авторизация и загрузка состояния выполняются в зависимостях до accept().
    Сессия БД на время соединения не удерживается.
    """
    session_id_str = str(game_session_id)

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
