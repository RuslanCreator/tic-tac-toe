import uuid

from fastapi import APIRouter, Depends, Path, status

from application.use_cases import (
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    GetFinishedSessionsUseCase,
    GetGameSessionUseCase,
    GetPlayerByUuidUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    LeaveGameUseCase,
    MakeMoveUseCase,
)
from di.composition import (
    get_create_pve_game_use_case,
    get_create_pvp_game_use_case,
    get_finished_sessions_use_case,
    get_game_session_use_case,
    get_join_pvp_game_use_case,
    get_leave_game_use_case,
    get_make_move_use_case,
    get_user_by_uuid_use_case,
    get_waiting_session_use_case,
)
from web.auth.guard import get_current_player_id
from web.mapper import WebGameMapper
from web.schema import (
    AvailableSessionsResponse,
    FinishedSessionsResponse,
    GameResponse,
    MoveRequest,
    UserResponse,
)
from web.ws.manager import notifier

game_router = APIRouter(prefix="/game", tags=["Игровой процесс"])


@game_router.post(
    "/new/pve", response_model=GameResponse, status_code=status.HTTP_201_CREATED
)
async def create_pve_game_session(
    use_case: CreatePvEGameUseCase = Depends(get_create_pve_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    new_game_session = await use_case.execute(player_id=current_player_id)
    return WebGameMapper.to_web_response(domain_game_session=new_game_session)


@game_router.post(
    "/new/pvp", response_model=GameResponse, status_code=status.HTTP_201_CREATED
)
async def create_pvp_game(
    use_case: CreatePvPGameUseCase = Depends(get_create_pvp_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    new_game_session = await use_case.execute(player_id=current_player_id)
    return WebGameMapper.to_web_response(domain_game_session=new_game_session)


@game_router.get("/open_lobby", response_model=AvailableSessionsResponse)
async def get_available_session(
    use_case: GetWaitingSessionsUseCase = Depends(get_waiting_session_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    domain_infos = await use_case.execute()

    return WebGameMapper.to_available_sessions_response(domain_infos)


@game_router.get("/finished", response_model=FinishedSessionsResponse)
async def get_finished_sessions(
    use_case: GetFinishedSessionsUseCase = Depends(get_finished_sessions_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    infos = await use_case.execute(player_id=current_player_id)
    return WebGameMapper.to_finished_sessions_response(infos)


@game_router.get("/user/{user_uuid}", response_model=UserResponse)
async def get_user_by_uuid(
    user_uuid: uuid.UUID = Path(...),
    use_case: GetPlayerByUuidUseCase = Depends(get_user_by_uuid_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    return await use_case.execute(player_id=str(user_uuid))


@game_router.post("/{game_session_id}/join", response_model=GameResponse)
async def join_pvp_game(
    game_session_id: uuid.UUID = Path(...),
    use_case: JoinPvPGameUseCase = Depends(get_join_pvp_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    updated_game_session = await use_case.execute(
        game_session_id=str(game_session_id), player_id=current_player_id
    )
    await notifier.broadcast(
        game_session_id=str(game_session_id),
        message=WebGameMapper.to_web_response(updated_game_session).model_dump(
            mode="json"
        ),
    )

    return WebGameMapper.to_web_response(domain_game_session=updated_game_session)


@game_router.post("/{game_session_id}/move", response_model=GameResponse)
async def make_move(
    request: MoveRequest,
    game_session_id: uuid.UUID = Path(...),
    use_case: MakeMoveUseCase = Depends(get_make_move_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
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

    return WebGameMapper.to_web_response(domain_game_session=updated_game_session)


@game_router.post("/{game_session_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_game(
    game_session_id: uuid.UUID = Path(...),
    use_case: LeaveGameUseCase = Depends(get_leave_game_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    updated_game_session = await use_case.execute(
        game_session_id=str(game_session_id), player_id=current_player_id
    )
    if updated_game_session is None:
        await notifier.broadcast(
            game_session_id=str(game_session_id),
            message={
                "type": "GAME_DELETED",
                "detail": "Игра удалена.",
            },
        )
        return

    await notifier.broadcast(
        game_session_id=str(game_session_id),
        message=WebGameMapper.to_web_response(updated_game_session).model_dump(
            mode="json"
        ),
    )


@game_router.get("/{game_session_id}", response_model=GameResponse)
async def get_current_game(
    game_session_id: uuid.UUID = Path(...),
    use_case: GetGameSessionUseCase = Depends(get_game_session_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    game_session = await use_case.execute(
        game_session_id=str(game_session_id), player_id=current_player_id
    )

    return WebGameMapper.to_web_response(domain_game_session=game_session)
