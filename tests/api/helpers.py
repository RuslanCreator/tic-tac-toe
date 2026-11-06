from fastapi.testclient import TestClient


def signup(
    client: TestClient,
    login: str,
    password: str = "secret123",
):
    return client.post(
        "/auth/signup",
        json={"login": login, "password": password},
    )


def login(
    client: TestClient,
    login_name: str,
    password: str = "secret123",
) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/auth/login",
        json={"login": login_name, "password": password},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data, {"Authorization": f"Bearer {data['access_token']}"}


def signup_and_login(
    client: TestClient,
    login_name: str,
    password: str = "secret123",
) -> tuple[dict, dict[str, str]]:
    response = signup(client, login_name, password)
    assert response.status_code == 201, response.text
    return login(client, login_name, password)
