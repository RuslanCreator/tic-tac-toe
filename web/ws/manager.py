from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, game_session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if game_session_id not in self._active_connections:
            self._active_connections[game_session_id] = set()
        self._active_connections[game_session_id].add(websocket)

    def disconnect(self, game_session_id: str, websocket: WebSocket) -> None:
        if game_session_id in self._active_connections:
            self._active_connections[game_session_id].discard(websocket)
            if not self._active_connections[game_session_id]:
                del self._active_connections[game_session_id]

    async def broadcast(self, game_session_id: str, message: dict) -> None:
        if game_session_id not in self._active_connections:
            return

        for connection in set(self._active_connections[game_session_id]):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(game_session_id, connection)


notifier = ConnectionManager()
