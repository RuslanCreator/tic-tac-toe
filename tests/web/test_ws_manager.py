from web.ws.manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("connection is broken")
        self.messages.append(message)


async def test_connect_accepts_and_broadcasts() -> None:
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect("game", websocket)  # type: ignore[arg-type]
    await manager.broadcast("game", {"status": "TURN_X"})

    assert websocket.accepted is True
    assert websocket.messages == [{"status": "TURN_X"}]
    assert manager._active_connections["game"] == {websocket}


async def test_broadcast_to_unknown_game_is_noop() -> None:
    manager = ConnectionManager()

    await manager.broadcast("missing", {"status": "TURN_X"})

    assert manager._active_connections == {}


async def test_disconnect_removes_empty_game() -> None:
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect("game", websocket)  # type: ignore[arg-type]
    manager.disconnect("game", websocket)  # type: ignore[arg-type]

    assert "game" not in manager._active_connections


async def test_broken_connection_is_dropped_on_broadcast() -> None:
    manager = ConnectionManager()
    broken = FakeWebSocket(fail=True)
    healthy = FakeWebSocket()

    await manager.connect("game", broken)  # type: ignore[arg-type]
    await manager.connect("game", healthy)  # type: ignore[arg-type]
    await manager.broadcast("game", {"status": "TURN_O"})

    assert manager._active_connections["game"] == {healthy}
    assert healthy.messages == [{"status": "TURN_O"}]
