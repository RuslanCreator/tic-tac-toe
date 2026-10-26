from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from application.jwt_srvc import decode_access_token

security = HTTPBearer()


async def get_current_player_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Новый PlayerAuthenticator.
    Извлекает JWT-токен из заголовка Authorization (Bearer),
    проверяет его валидность без запроса к БД и возвращает ID игрока.
    """
    token = credentials.credentials
    try:
        player_id = decode_access_token(token)

        return player_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
