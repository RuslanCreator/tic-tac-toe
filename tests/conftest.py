from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from application.jwt_service import JWTService
from di.composition import (
    get_context,
    get_db_session,
    get_game_session_repository,
    get_player_repository,
)
from tests.fakes import (
    FakeAppContext,
    InMemoryGameSessionRepository,
    InMemoryPlayerRepository,
)
from web.app import create_app

SECRET = "test-secret-key-that-is-long-enough-123"


@pytest.fixture
def player_repository() -> InMemoryPlayerRepository:
    return InMemoryPlayerRepository()


@pytest.fixture
def game_session_repository(
    player_repository: InMemoryPlayerRepository,
) -> InMemoryGameSessionRepository:
    return InMemoryGameSessionRepository(player_repository=player_repository)


@pytest.fixture
def app_context(player_repository: InMemoryPlayerRepository) -> FakeAppContext:
    return FakeAppContext(
        jwt_service=JWTService(
            secret_key=SECRET,
            algorithm="HS256",
            expire_minutes=60,
        )
    )


@pytest.fixture
def app(
    app_context: FakeAppContext,
    player_repository: InMemoryPlayerRepository,
    game_session_repository: InMemoryGameSessionRepository,
):
    application = create_app(init_db=False, context=app_context)

    async def override_db_session() -> AsyncGenerator[None, None]:
        yield None

    application.dependency_overrides[get_context] = lambda: app_context
    application.dependency_overrides[get_db_session] = override_db_session
    application.dependency_overrides[get_player_repository] = lambda: player_repository
    application.dependency_overrides[get_game_session_repository] = lambda: (
        game_session_repository
    )
    return application


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
