from datetime import datetime, timedelta, timezone

import jwt

from application.errors import AuthenticationError


class JWTService:
    def __init__(self, secret_key: str, algorithm: str, expire_minutes: int) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_access_token(self, player_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._expire_minutes)

        to_encode = {"sub": player_id, "exp": expire}
        encoded_jwt = jwt.encode(to_encode, self._secret_key, algorithm=self._algorithm)
        return encoded_jwt

    def decode_access_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            player_id: str = payload.get("sub")
            if not isinstance(player_id, str) or not player_id:
                raise AuthenticationError("В структуре токена отсутствует поле 'sub'")

            return player_id
        except jwt.ExpiredSignatureError:
            raise AuthenticationError(
                "Срок действия токена истек. Авторизуйтесь заново."
            ) from None
        except jwt.InvalidTokenError:
            raise AuthenticationError(
                "Предоставлен невалидный или подделанный токен."
            ) from None
