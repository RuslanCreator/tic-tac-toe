from di.composition import get_ws_game_session
from tests.api.helpers import signup_and_login


def test_websocket_sends_initial_game_state(
    client,
    app,
    game_session_repository,
) -> None:
    _, headers = signup_and_login(client, "alice")
    response = client.post("/game/new/pve", headers=headers)
    assert response.status_code == 201
    game_data = response.json()
    game_id = game_data["game_session_id"]
    game = game_session_repository.sessions[game_id]

    async def override_ws_session():
        return game

    app.dependency_overrides[get_ws_game_session] = override_ws_session

    with client.websocket_connect(f"/game/{game_id}/ws") as websocket:
        message = websocket.receive_json()

    assert message["game_session_id"] == game_id
    assert message["mode"] == "PVE"
    assert message["status"] == "TURN_X"
    assert len(message["board"]) == 9
