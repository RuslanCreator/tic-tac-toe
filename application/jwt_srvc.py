from datetime import datetime, timedelta, timezone

import jwt

# os.getenv
SECRET_KEY = "SUPER_SECRET_GAME_KEY_DO_NOT_SHARE_ANYWHERE_№1!!!"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(player_id: str) -> str:
    exire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"sub": player_id, "exp": exire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        player_id: str = payload.get("sub")
        if player_id is None:
            raise ValueError(("В структуре токена отсутствует поле 'sub'"))

        return player_id
    except jwt.ExpiredSignatureError:
        raise ValueError("Срок действия токена истек. Авторизуйтесь заново.")
    except jwt.InvalidTokenError:
        raise ValueError("Предоставлен невалидный или подделанный токен.")
