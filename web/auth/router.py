from fastapi import APIRouter, Depends, status

from application.jwt_service import JWTService
from application.use_cases import (
    AuthenticatePlayerUseCase,
    GetPlayerByUuidUseCase,
    SignUpUseCase,
)
from di.composition import (
    get_authenticate_player_use_case,
    get_jwt_service,
    get_signup_use_case,
    get_user_by_uuid_use_case,
)
from web.auth.guard import get_current_player_id
from web.schema import AuthResponse, LoginRequest, SignUpRequest, UserResponse

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request_data: SignUpRequest,
    use_case: SignUpUseCase = Depends(get_signup_use_case),
):
    await use_case.execute(login=request_data.login, password=request_data.password)
    return {"status": "success", "message": "Игрок успешно зарегистрирован"}


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    use_case: AuthenticatePlayerUseCase = Depends(get_authenticate_player_use_case),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    player = await use_case.execute(login=request.login, password=request.password)
    token = jwt_service.create_access_token(player_id=player.id)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        player_id=player.id,
        login=player.login,
    )


@auth_router.get("/me", response_model=UserResponse)
async def me(
    current_player_id: str = Depends(get_current_player_id),
    use_case: GetPlayerByUuidUseCase = Depends(get_user_by_uuid_use_case),
):
    return await use_case.execute(player_id=current_player_id)
