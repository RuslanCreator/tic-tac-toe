from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from application.jwt_service import JWTService
from application.use_cases import AuthenticatePlayerUseCase, SignUpUseCase
from di.composition import (
    get_authenticate_player_use_case,
    get_db_session,
    get_jwt_service,
    get_signup_use_case,
)
from web.schema import AuthResponse, LoginRequest, SignUpRequest

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request_data: SignUpRequest,
    use_case: SignUpUseCase = Depends(get_signup_use_case),
    session: AsyncSession = Depends(get_db_session),
):
    await use_case.execute(login=request_data.login, password=request_data.password)
    await session.commit()

    return {"status": "success", "message": "Игрок успешно зарегистрирован"}


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    use_case: AuthenticatePlayerUseCase = Depends(get_authenticate_player_use_case),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    player_id = await use_case.execute(login=request.login, password=request.password)
    token = jwt_service.create_access_token(player_id=player_id)

    return AuthResponse(access_token=token, token_type="bearer")
