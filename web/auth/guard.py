from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from application.errors import AuthenticationError
from application.jwt_service import JWTService
from di.composition import get_jwt_service

security = HTTPBearer(auto_error=False)


async def get_current_player_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> str:
    """
    Извлекает JWT-токен из заголовка Authorization (Bearer),
    проверяет его валидность без запроса к БД и возвращает ID игрока.
    """
    if credentials is None:
        raise AuthenticationError(
            "Не передан заголовок Authorization: Bearer <token>"
        )

    return jwt_service.decode_access_token(credentials.credentials)
