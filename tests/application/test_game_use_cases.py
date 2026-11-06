import pytest

from application.errors import ConflictError, ForbiddenError, NotFoundError
from application.strategies import (
    MoveResponderRegistry,
    PveMoveResponder,
    PvpMoveResponder,
)
from application.use_cases import (
    CreatePvEGameUseCase,
    CreatePvPGameUseCase,
    GetFinishedSessionsUseCase,
    GetGameSessionUseCase,
    GetWaitingSessionsUseCase,
    JoinPvPGameUseCase,
    LeaveGameUseCase,
    MakeMoveUseCase,
)
from domain.entities.game_session import GameMode, GameSession, GameSessionState
from domain.entities.player import BOT_PLAYER_ID
from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError
from tests.fakes import FakeAIPlayer, InMemoryGameSessionRepository

X = "player-x"  # noqa: E741
O = "player-o"  # noqa: E741


def make_registry(ai: FakeAIPlayer | None = None) -> MoveResponderRegistry:
    return MoveResponderRegistry(
        {
            GameMode.PVP: PvpMoveResponder(),
            GameMode.PVE: PveMoveResponder(ai or FakeAIPlayer()),
        }
    )


async def create_pvp(repository: InMemoryGameSessionRepository) -> GameSession:
    return await CreatePvPGameUseCase(repository).execute(X)


async def create_pve(repository: InMemoryGameSessionRepository) -> GameSession:
    return await CreatePvEGameUseCase(repository).execute(X)


async def create_ready_pvp(
    repository: InMemoryGameSessionRepository,
) -> GameSession:
    game = await create_pvp(repository)
    await JoinPvPGameUseCase(repository).execute(game.id, O)
    session = await repository.get_by_id(game.id)
    assert session is not None
    return session


async def play(
    use_case: MakeMoveUseCase,
    game_session_id: str,
    moves: list[tuple[int, int, str]],
) -> GameSession:
    session: GameSession | None = None
    for row, col, player in moves:
        session = await use_case.execute(game_session_id, row, col, player)
    assert session is not None
    return session


async def test_create_pve_game() -> None:
    repository = InMemoryGameSessionRepository()

    session = await create_pve(repository)

    assert session.mode == GameMode.PVE
    assert session.player_x_id == X
    assert session.player_o_id == BOT_PLAYER_ID
    assert session.status == GameSessionState.TURN_X
    assert session.id in repository.sessions


async def test_create_pvp_game() -> None:
    repository = InMemoryGameSessionRepository()

    session = await create_pvp(repository)

    assert session.mode == GameMode.PVP
    assert session.player_x_id == X
    assert session.player_o_id is None
    assert session.status == GameSessionState.WAITING


async def test_join_pvp_game() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pvp(repository)

    joined = await JoinPvPGameUseCase(repository).execute(game.id, O)

    assert joined.player_o_id == O
    assert joined.status == GameSessionState.TURN_X
    assert joined.mode == GameMode.PVP


async def test_join_returns_existing_session_for_participant() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pvp(repository)

    joined = await JoinPvPGameUseCase(repository).execute(game.id, X)

    assert joined.player_o_id is None
    assert joined.status == GameSessionState.WAITING


async def test_join_missing_game_raises_not_found() -> None:
    repository = InMemoryGameSessionRepository()

    with pytest.raises(NotFoundError):
        await JoinPvPGameUseCase(repository).execute("missing", O)


async def test_join_pve_game_is_rejected() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pve(repository)

    with pytest.raises(ConflictError):
        await JoinPvPGameUseCase(repository).execute(game.id, O)


async def test_join_full_game_is_rejected() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)

    with pytest.raises(ConflictError):
        await JoinPvPGameUseCase(repository).execute(game.id, "third-player")


async def test_join_finished_game_is_rejected() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    await LeaveGameUseCase(repository).execute(game.id, O)

    with pytest.raises(ConflictError):
        await JoinPvPGameUseCase(repository).execute(game.id, "third-player")


async def test_pvp_move_does_not_call_ai() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    ai = FakeAIPlayer(error=AssertionError("AI must not be called"))
    use_case = MakeMoveUseCase(repository, make_registry(ai))

    updated = await use_case.execute(game.id, 0, 0, X)

    assert updated.status == GameSessionState.TURN_O
    assert ai.calls == []
    stored = await repository.get_by_id(game.id)
    assert stored is not None
    assert stored.status == GameSessionState.TURN_O


async def test_pve_move_calls_ai_and_applies_bot_move() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pve(repository)
    ai = FakeAIPlayer(move=(1, 1))
    use_case = MakeMoveUseCase(repository, make_registry(ai))

    updated = await use_case.execute(game.id, 0, 0, X)

    assert len(ai.calls) == 1
    _, ai_sign = ai.calls[0]
    assert ai_sign == CellState.SIGN_O
    assert updated.board.grid[0] == CellState.SIGN_X
    assert updated.board.grid[4] == CellState.SIGN_O
    assert updated.status == GameSessionState.TURN_X


async def test_pve_does_not_call_ai_after_human_win() -> None:
    repository = InMemoryGameSessionRepository()
    board = PlayingBoard.from_int_list([1, 1, 0, 2, 2, 0, 0, 0, 0])
    game = GameSession.restore(
        id="game",
        board=board,
        player_x_id=X,
        player_o_id=BOT_PLAYER_ID,
        status=GameSessionState.TURN_X,
    )
    await repository.add(game)
    ai = FakeAIPlayer(move=(2, 2))
    use_case = MakeMoveUseCase(repository, make_registry(ai))

    updated = await use_case.execute(game.id, 0, 2, X)

    assert updated.status == GameSessionState.WON_X
    assert ai.calls == []


async def test_move_missing_game_raises_not_found() -> None:
    repository = InMemoryGameSessionRepository()
    use_case = MakeMoveUseCase(repository, make_registry())

    with pytest.raises(NotFoundError):
        await use_case.execute("missing", 0, 0, X)


async def test_move_by_non_participant_is_forbidden() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = MakeMoveUseCase(repository, make_registry())

    with pytest.raises(ForbiddenError):
        await use_case.execute(game.id, 0, 0, "stranger")


async def test_move_out_of_turn_is_rejected() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = MakeMoveUseCase(repository, make_registry())

    with pytest.raises(DomainError):
        await use_case.execute(game.id, 0, 0, O)


async def test_move_after_finish_is_rejected() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = MakeMoveUseCase(repository, make_registry())
    await play(
        use_case,
        game.id,
        [
            (0, 0, X),
            (1, 0, O),
            (0, 1, X),
            (1, 1, O),
            (0, 2, X),
        ],
    )

    with pytest.raises(DomainError):
        await use_case.execute(game.id, 2, 2, O)


def test_registry_rejects_incomplete_modes() -> None:
    with pytest.raises(ValueError):
        MoveResponderRegistry({GameMode.PVP: PvpMoveResponder()})


async def test_leave_waiting_lobby_deletes_game() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pvp(repository)

    result = await LeaveGameUseCase(repository).execute(game.id, X)

    assert result is None
    assert game.id not in repository.sessions


async def test_leave_pve_game_deletes_game() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_pve(repository)

    result = await LeaveGameUseCase(repository).execute(game.id, X)

    assert result is None
    assert game.id not in repository.sessions


async def test_leave_active_pvp_by_o_gives_win_to_x() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)

    result = await LeaveGameUseCase(repository).execute(game.id, O)

    assert result is not None
    assert result.status == GameSessionState.WON_X
    stored = await repository.get_by_id(game.id)
    assert stored is not None
    assert stored.status == GameSessionState.WON_X


async def test_leave_active_pvp_by_x_gives_win_to_o() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)

    result = await LeaveGameUseCase(repository).execute(game.id, X)

    assert result is not None
    assert result.status == GameSessionState.WON_O


async def test_leave_finished_game_does_not_delete_it() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = MakeMoveUseCase(repository, make_registry())
    await play(
        use_case,
        game.id,
        [
            (0, 0, X),
            (1, 0, O),
            (0, 1, X),
            (1, 1, O),
            (0, 2, X),
        ],
    )

    result = await LeaveGameUseCase(repository).execute(game.id, X)

    assert result is not None
    assert result.status == GameSessionState.WON_X
    assert game.id in repository.sessions


async def test_leave_by_non_participant_is_forbidden() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)

    with pytest.raises(ForbiddenError):
        await LeaveGameUseCase(repository).execute(game.id, "stranger")


async def test_leave_missing_game_raises_not_found() -> None:
    repository = InMemoryGameSessionRepository()

    with pytest.raises(NotFoundError):
        await LeaveGameUseCase(repository).execute("missing", X)


async def test_get_game_session_checks_participation() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = GetGameSessionUseCase(repository)

    found = await use_case.execute(game.id, X)
    assert found.id == game.id

    with pytest.raises(ForbiddenError):
        await use_case.execute(game.id, "stranger")

    with pytest.raises(NotFoundError):
        await use_case.execute("missing", X)


async def test_get_waiting_sessions() -> None:
    repository = InMemoryGameSessionRepository({X: "alice"})
    game = await create_pvp(repository)

    sessions = await GetWaitingSessionsUseCase(repository).execute()

    assert len(sessions) == 1
    assert sessions[0].game_session_id == game.id
    assert sessions[0].creator_login == "alice"


async def test_get_finished_sessions() -> None:
    repository = InMemoryGameSessionRepository()
    game = await create_ready_pvp(repository)
    use_case = MakeMoveUseCase(repository, make_registry())
    await play(
        use_case,
        game.id,
        [
            (0, 0, X),
            (1, 0, O),
            (0, 1, X),
            (1, 1, O),
            (0, 2, X),
        ],
    )

    finished_for_x = await GetFinishedSessionsUseCase(repository).execute(X)
    finished_for_o = await GetFinishedSessionsUseCase(repository).execute(O)

    assert finished_for_x[0].result == "WIN"
    assert finished_for_o[0].result == "LOSE"
