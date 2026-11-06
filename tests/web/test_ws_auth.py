import pytest
from fastapi import WebSocketException

from application.errors import AuthenticationError
from application.jwt_service import JWTService
from di.composition import (
    WS_TOKEN_PROTOCOL,
    _extract_ws_token,
    get_ws_player_id,
)

SECRET = "test-secret-key-that-is-long-enough-123"


class FakeWebSocket:
    def __init__(self, protocols: str = "") -> None:
        self.headers = {"sec-websocket-protocol": protocols}


def test_extract_token_from_subprotocol() -> None:
    websocket = FakeWebSocket(f"{WS_TOKEN_PROTOCOL}, token-123")

    assert _extract_ws_token(websocket, None) == "token-123"


def test_extract_token_falls_back_to_query() -> None:
    websocket = FakeWebSocket(WS_TOKEN_PROTOCOL)

    assert _extract_ws_token(websocket, "query-token") == "query-token"


def test_extract_token_requires_token() -> None:
    websocket = FakeWebSocket("")

    with pytest.raises(AuthenticationError):
        _extract_ws_token(websocket, None)


async def test_invalid_ws_token_is_rejected() -> None:
    service = JWTService(secret_key=SECRET, algorithm="HS256", expire_minutes=60)

    with pytest.raises(WebSocketException):
        await get_ws_player_id(FakeWebSocket(), "not-a-token", service)  # type: ignore[arg-type]
