from datetime import UTC, datetime, timedelta

import jwt
import pytest

from application.errors import AuthenticationError
from application.jwt_service import JWTService

SECRET = "test-secret-key-that-is-long-enough-123"


def test_token_roundtrip() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=60)

    token = service.create_access_token("player-1")

    assert service.decode_access_token(token) == "player-1"


def test_expired_token_is_rejected() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=-1)
    token = service.create_access_token("player-1")

    with pytest.raises(AuthenticationError):
        service.decode_access_token(token)


def test_invalid_token_is_rejected() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=60)

    with pytest.raises(AuthenticationError):
        service.decode_access_token("not-a-jwt")


def test_token_signed_with_another_secret_is_rejected() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=60)
    token = jwt.encode(
        {
            "sub": "player-1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "another-secret-key-that-is-long-enough",
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        service.decode_access_token(token)


def test_token_without_sub_is_rejected() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=60)
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        service.decode_access_token(token)
