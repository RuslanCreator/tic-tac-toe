import uuid

from tests.api.helpers import signup_and_login


def create_pve(client, headers: dict[str, str]) -> dict:
    response = client.post("/game/new/pve", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def create_pvp(client, headers: dict[str, str]) -> dict:
    response = client.post("/game/new/pvp", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def join(client, game_id: str, headers: dict[str, str]) -> dict:
    response = client.post(f"/game/{game_id}/join", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def move(
    client,
    game_id: str,
    headers: dict[str, str],
    row: int,
    col: int,
) -> dict:
    response = client.post(
        f"/game/{game_id}/move",
        headers=headers,
        json={"row": row, "col": col},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_pve_returns_complete_state(client) -> None:
    alice, headers = signup_and_login(client, "alice")

    game = create_pve(client, headers)

    assert game["mode"] == "PVE"
    assert game["status"] == "TURN_X"
    assert game["grid_size"] == 3
    assert len(game["board"]) == 9
    assert game["player_x_id"] == alice["player_id"]
    assert game["player_o_id"] == "bot"
    assert game["current_player_id"] == alice["player_id"]
    assert game["is_finished"] is False


def test_create_pvp_starts_waiting(client) -> None:
    alice, headers = signup_and_login(client, "alice")

    game = create_pvp(client, headers)

    assert game["mode"] == "PVP"
    assert game["status"] == "WAITING"
    assert game["player_o_id"] is None
    assert game["current_player_id"] is None


def test_unified_pve_move_applies_bot_answer(client) -> None:
    _, headers = signup_and_login(client, "alice")
    game = create_pve(client, headers)

    updated = move(client, game["game_session_id"], headers, 0, 0)

    assert updated["board"][0] == "X"
    assert updated["board"][1] == "O"
    assert updated["status"] == "TURN_X"


def test_old_move_endpoints_are_gone(client) -> None:
    _, headers = signup_and_login(client, "alice")
    game = create_pve(client, headers)
    game_id = game["game_session_id"]

    assert (
        client.post(
            f"/game/{game_id}/move/pve",
            headers=headers,
            json={"row": 0, "col": 0},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/game/{game_id}/move/pvp",
            headers=headers,
            json={"row": 0, "col": 0},
        ).status_code
        == 404
    )


def test_pvp_join_and_moves(client) -> None:
    alice, alice_headers = signup_and_login(client, "alice")
    bob, bob_headers = signup_and_login(client, "bob")
    game = create_pvp(client, alice_headers)
    game_id = game["game_session_id"]

    joined = join(client, game_id, bob_headers)
    assert joined["player_o_id"] == bob["player_id"]
    assert joined["status"] == "TURN_X"
    assert joined["current_player_id"] == alice["player_id"]

    after_x = move(client, game_id, alice_headers, 0, 0)
    assert after_x["status"] == "TURN_O"
    assert after_x["current_player_id"] == bob["player_id"]

    after_o = move(client, game_id, bob_headers, 1, 1)
    assert after_o["status"] == "TURN_X"
    assert after_o["current_player_id"] == alice["player_id"]


def test_non_participant_cannot_move(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    _, carol_headers = signup_and_login(client, "carol")
    game = create_pvp(client, alice_headers)
    game_id = game["game_session_id"]
    join(client, game_id, bob_headers)

    response = client.post(
        f"/game/{game_id}/move",
        headers=carol_headers,
        json={"row": 0, "col": 0},
    )

    assert response.status_code == 403


def test_move_out_of_turn_returns_400(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    game = create_pvp(client, alice_headers)
    game_id = game["game_session_id"]
    join(client, game_id, bob_headers)

    response = client.post(
        f"/game/{game_id}/move",
        headers=bob_headers,
        json={"row": 0, "col": 0},
    )

    assert response.status_code == 400


def test_open_lobby_lists_and_disappears_after_join(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    game = create_pvp(client, alice_headers)

    lobbies = client.get("/game/open_lobby", headers=bob_headers)
    assert lobbies.status_code == 200
    assert lobbies.json()["sessions"][0]["game_session_id"] == game["game_session_id"]
    assert lobbies.json()["sessions"][0]["creator_login"] == "alice"

    join(client, game["game_session_id"], bob_headers)

    lobbies_after = client.get("/game/open_lobby", headers=bob_headers)
    assert lobbies_after.json()["sessions"] == []


def test_host_leave_deletes_waiting_lobby(client) -> None:
    _, headers = signup_and_login(client, "alice")
    game = create_pvp(client, headers)
    game_id = game["game_session_id"]

    response = client.post(f"/game/{game_id}/leave", headers=headers)

    assert response.status_code == 204
    assert client.get(f"/game/{game_id}", headers=headers).status_code == 404


def test_guest_leave_active_game_forfeits(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    game = create_pvp(client, alice_headers)
    game_id = game["game_session_id"]
    join(client, game_id, bob_headers)

    response = client.post(f"/game/{game_id}/leave", headers=bob_headers)

    assert response.status_code == 204
    state = client.get(f"/game/{game_id}", headers=alice_headers)
    assert state.status_code == 200
    assert state.json()["status"] == "WON_X"


def test_leave_by_non_participant_returns_403(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    _, carol_headers = signup_and_login(client, "carol")
    game = create_pvp(client, alice_headers)
    join(client, game["game_session_id"], bob_headers)

    response = client.post(
        f"/game/{game['game_session_id']}/leave",
        headers=carol_headers,
    )

    assert response.status_code == 403


def test_finished_history_and_x_win(client) -> None:
    _, alice_headers = signup_and_login(client, "alice")
    _, bob_headers = signup_and_login(client, "bob")
    game = create_pvp(client, alice_headers)
    game_id = game["game_session_id"]
    join(client, game_id, bob_headers)

    move(client, game_id, alice_headers, 0, 0)
    move(client, game_id, bob_headers, 1, 0)
    move(client, game_id, alice_headers, 0, 1)
    move(client, game_id, bob_headers, 1, 1)
    final = move(client, game_id, alice_headers, 0, 2)

    assert final["status"] == "WON_X"
    assert final["is_finished"] is True

    alice_finished = client.get("/game/finished", headers=alice_headers)
    bob_finished = client.get("/game/finished", headers=bob_headers)

    assert alice_finished.status_code == 200
    assert alice_finished.json()["sessions"][0]["result"] == "WIN"
    assert bob_finished.json()["sessions"][0]["result"] == "LOSE"


def test_missing_game_returns_404(client) -> None:
    _, headers = signup_and_login(client, "alice")

    response = client.get(f"/game/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


def test_game_endpoints_require_auth(client) -> None:
    assert client.post("/game/new/pve").status_code == 401
    assert client.get(f"/game/{uuid.uuid4()}").status_code == 401
