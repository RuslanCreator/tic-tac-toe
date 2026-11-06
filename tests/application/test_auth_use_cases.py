import pytest

from application.errors import AuthenticationError, ConflictError
from application.use_cases import AuthenticatePlayerUseCase, SignUpUseCase
from tests.fakes import FakePasswordHasher, InMemoryPlayerRepository


def make_use_cases(
    repository: InMemoryPlayerRepository | None = None,
) -> tuple[SignUpUseCase, AuthenticatePlayerUseCase, InMemoryPlayerRepository]:
    repo = repository or InMemoryPlayerRepository()
    hasher = FakePasswordHasher()
    signup = SignUpUseCase(player_repository=repo, crypto_service=hasher)
    authenticate = AuthenticatePlayerUseCase(
        player_repository=repo, crypto_service=hasher
    )
    return signup, authenticate, repo


async def test_signup_saves_player_with_password_hash() -> None:
    signup, _, repository = make_use_cases()

    player_id = await signup.execute(login="alice", password="secret")

    assert repository.players[player_id].login == "alice"
    assert repository.password_hashes[player_id] == "hashed::secret"


async def test_signup_rejects_duplicate_login() -> None:
    signup, _, _ = make_use_cases()
    await signup.execute(login="alice", password="secret")

    with pytest.raises(ConflictError):
        await signup.execute(login="alice", password="other-secret")


async def test_authenticate_returns_player() -> None:
    signup, authenticate, _ = make_use_cases()
    player_id = await signup.execute(login="alice", password="secret")

    player = await authenticate.execute(login="alice", password="secret")

    assert player.id == player_id
    assert player.login == "alice"


async def test_authenticate_rejects_unknown_login() -> None:
    _, authenticate, _ = make_use_cases()

    with pytest.raises(AuthenticationError):
        await authenticate.execute(login="unknown", password="secret")


async def test_authenticate_rejects_wrong_password() -> None:
    signup, authenticate, _ = make_use_cases()
    await signup.execute(login="alice", password="secret")

    with pytest.raises(AuthenticationError):
        await authenticate.execute(login="alice", password="wrong")
