from fastapi import APIRouter, Depends, HTTPException, status

from application.jwt_srvc import create_access_token
from application.use_cases import AuthenticatePlayerUseCase, SignUpUseCase
from di.container import get_authenticate_player_use_case, get_signup_use_case
from web.schema import AuthResponse, LoginRequest, SignUpRequest

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request_data: SignUpRequest, use_case: SignUpUseCase = Depends(get_signup_use_case)
):
    try:
        await use_case.execute(login=request_data.login, password=request_data.password)
        return {"status": "success", "message": "Игрок успешно зарегистрирован"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    use_case: AuthenticatePlayerUseCase = Depends(get_authenticate_player_use_case),
):
    try:
        player_id = await use_case.execute(
            login=request.login, password=request.password
        )
        token = create_access_token(player_id=player_id)

        return AuthResponse(access_token=token, token_type="bearer")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
