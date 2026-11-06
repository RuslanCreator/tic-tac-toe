from di.composition import get_context
from tests.api.helpers import login, signup, signup_and_login
from tests.fakes import FakeAppContext


def test_signup_login_and_me(client) -> None:
    response = signup(client, "alice")
    assert response.status_code == 201

    login_data, headers = login(client, "alice")
    assert login_data["token_type"] == "bearer"
    assert login_data["login"] == "alice"
    assert login_data["player_id"]

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["login"] == "alice"
    assert me.json()["id"] == login_data["player_id"]


def test_duplicate_signup_returns_409(client) -> None:
    assert signup(client, "alice").status_code == 201

    response = signup(client, "alice")

    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_wrong_password_returns_401_with_challenge(client) -> None:
    signup(client, "alice")

    response = client.post(
        "/auth/login",
        json={"login": "alice", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_without_token_returns_401(client) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_invalid_token_returns_401(client) -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert response.status_code == 401


def test_short_password_returns_422(client) -> None:
    response = client.post(
        "/auth/signup",
        json={"login": "alice", "password": "123"},
    )

    assert response.status_code == 422


def test_health(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_down(client, app, app_context) -> None:
    broken_context = FakeAppContext(
        jwt_service=app_context.jwt_service,
        healthy=False,
    )
    app.dependency_overrides[get_context] = lambda: broken_context

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_player_can_be_found_by_uuid(client) -> None:
    alice_login, alice_headers = signup_and_login(client, "alice")
    bob_login, _ = signup_and_login(client, "bob")

    response = client.get(
        f"/game/user/{bob_login['player_id']}",
        headers=alice_headers,
    )

    assert response.status_code == 200
    assert response.json()["login"] == "bob"
    assert alice_login["player_id"] != bob_login["player_id"]
