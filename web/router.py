import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from application.jwt_srvc import decode_access_token
from application.use_cases import (
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    DeleteGameSessionUseCase,
    GetGameSessionUseCase,
    GetPlayerByUuidUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    MakeMovePvEUseCase,
    MakeMovePvPUseCase,
)
from di.container import (
    get_create_pve_game_use_case,
    get_create_pvp_game_use_case,
    get_delete_session_use_case,
    get_game_session_use_case,
    get_join_pvp_game_use_case,
    get_make_move_pve_use_case,
    get_make_move_pvp_use_case,
    get_user_by_uuid_use_case,
    get_waiting_session_use_case,
)
from web.auth_guard import get_current_player_id
from web.mapper import WebGameMapper
from web.schema import (
    AvailableSessionsResponse,
    GameResponse,
    MoveRequest,
    UserResponse,
)
from web.websoc_manager import notifier

game_router = APIRouter(prefix="/game", tags=["Игровой процесс"])


@game_router.websocket("/{game_session_id}/ws")
async def game_websocket_endpoint(
    websocket: WebSocket,
    game_session_id: uuid.UUID = Path(...),
    token: str = Query(...),
    use_case: GetGameSessionUseCase = Depends(get_game_session_use_case),
):
    session_id_str = str(game_session_id)
    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notifier.connect(game_session_id=session_id_str, websocket=websocket)

    game_session = await use_case.execute(game_session_id=session_id_str)
    if game_session:
        await websocket.send_json(
            WebGameMapper.to_web_response(game_session).model_dump(mode="json")
        )

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        notifier.disconnect(game_session_id=session_id_str, websocket=websocket)


@game_router.post(
    "/new/pve", response_model=GameResponse, status_code=status.HTTP_201_CREATED
)
async def create_pve_game_session(
    use_case: CreatePvEGameUseCase = Depends(get_create_pve_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        new_game_session = await use_case.execute(player_id=current_player_id)

        return WebGameMapper.to_web_response(domain_game_session=new_game_session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось создать PvE игровую сессию: {str(e)}",
        )


@game_router.post("/{game_session_id}/move/pve", response_model=GameResponse)
async def make_move_pve(
    request: MoveRequest,
    game_session_id: uuid.UUID = Path(...),
    use_case: MakeMovePvEUseCase = Depends(get_make_move_pve_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        updated_game_session = await use_case.execute(
            game_session_id=str(game_session_id),
            player_id=current_player_id,
            row=request.row,
            col=request.col,
        )

        return WebGameMapper.to_web_response(domain_game_session=updated_game_session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при совершении PvE хода: {str(e)}",
        )


@game_router.get("/open_lobby", response_model=AvailableSessionsResponse)
async def get_available_session(
    use_case: GetWaitingSessionsUseCase = Depends(get_waiting_session_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        domain_infos = await use_case.execute()

        return WebGameMapper.to_available_sessions_response(domain_infos)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось получить список комнат: {str(e)}",
        )


@game_router.post(
    "/new/pvp", response_model=GameResponse, status_code=status.HTTP_201_CREATED
)
async def create_pvp_game(
    use_case: CreatePvPGameUseCase = Depends(get_create_pvp_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        new_game_session = await use_case.execute(player_id=current_player_id)
        return WebGameMapper.to_web_response(domain_game_session=new_game_session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось создать PvP лобби: {str(e)}",
        )


@game_router.post("/{game_session_id}/move/pvp", status_code=status.HTTP_204_NO_CONTENT)
async def make_move_pvp(
    request: MoveRequest,
    game_session_id: uuid.UUID = Path(...),
    use_case: MakeMovePvPUseCase = Depends(get_make_move_pvp_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        updated_game_session = await use_case.execute(
            game_session_id=str(game_session_id),
            player_id=current_player_id,
            row=request.row,
            col=request.col,
        )

        await notifier.broadcast(
            game_session_id=str(game_session_id),
            message=WebGameMapper.to_web_response(updated_game_session).model_dump(
                mode="json"
            ),
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при совершении PvP хода: {str(e)}",
        )


@game_router.post("/{game_session_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_pvp_game(
    game_session_id: uuid.UUID = Path(...),
    use_case: JoinPvPGameUseCase = Depends(get_join_pvp_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        updated_game_session = await use_case.execute(
            game_session_id=str(game_session_id), player_id=current_player_id
        )

        await notifier.broadcast(
            game_session_id=str(game_session_id),
            message=WebGameMapper.to_web_response(updated_game_session).model_dump(
                mode="json"
            ),
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось подключиться к сессии: {str(e)}",
        )


@game_router.delete("/{game_session_id}/del", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game_session(
    game_session_id: uuid.UUID = Path(...),
    use_case: DeleteGameSessionUseCase = Depends(get_delete_session_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        await use_case.execute(
            game_session_id=str(game_session_id), player_id=current_player_id
        )

        await notifier.broadcast(
            game_session_id=str(game_session_id),
            message={
                "type": "GAME_DELETED",
                "detail": "Хост покинул матч, игра удалена.",
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось удалить игровую сессию: {str(e)}",
        )


@game_router.get("/{game_session_id}", response_model=GameResponse)
async def get_current_game(
    game_session_id: uuid.UUID = Path(...),
    use_case: GetGameSessionUseCase = Depends(get_game_session_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        game_session = await use_case.execute(game_session_id=str(game_session_id))

        return WebGameMapper.to_web_response(domain_game_session=game_session)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Игровая сессия не найдена: {str(e)}",
        )


@game_router.get("/user/{user_uuid}", response_model=UserResponse)
async def get_user_by_uuid(
    user_uuid: uuid.UUID = Path(...),
    use_case: GetPlayerByUuidUseCase = Depends(get_user_by_uuid_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    try:
        user_info = await use_case.execute(player_id=str(user_uuid))

        return user_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь не найден: {str(e)}",
        )
