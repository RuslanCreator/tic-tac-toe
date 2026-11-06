from datetime import UTC, datetime

import pytest

from domain.entities.game_session import GameMode, GameSession, GameSessionState
from domain.entities.player import BOT_PLAYER_ID
from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError

X = "player-x"  # noqa: E741
O = "player-o"  # noqa: E741


def ready_pvp() -> GameSession:
    session = GameSession.create_pvp(X)
    session.setup_match(O)
    return session


def test_create_pvp_starts_waiting() -> None:
    session = GameSession.create_pvp(X)

    assert session.status == GameSessionState.WAITING
    assert session.is_waiting is True
    assert session.player_x_id == X
    assert session.player_o_id is None
    assert session.mode == GameMode.PVP
    assert session.is_pve is False
    assert session.created_at.tzinfo is not None


def test_create_pve_starts_with_bot_turn() -> None:
    session = GameSession.create_pve(X)

    assert session.status == GameSessionState.TURN_X
    assert session.player_x_id == X
    assert session.player_o_id == BOT_PLAYER_ID
    assert session.mode == GameMode.PVE
    assert session.is_pve is True


@pytest.mark.parametrize("factory_name", ["create_pvp", "create_pve"])
def test_create_rejects_empty_player_id(factory_name: str) -> None:
    factory = getattr(GameSession, factory_name)

    with pytest.raises(DomainError):
        factory("")


def test_setup_match_starts_game() -> None:
    session = GameSession.create_pvp(X)
    session.setup_match(O)

    assert session.status == GameSessionState.TURN_X
    assert session.player_o_id == O
    assert session.current_player_id == X
    assert session.get_current_turn_sign() == CellState.SIGN_X
    assert session.mode == GameMode.PVP


def test_setup_match_rejects_non_waiting_session() -> None:
    session = GameSession.create_pve(X)

    with pytest.raises(DomainError):
        session.setup_match(O)


def test_setup_match_rejects_self_play() -> None:
    session = GameSession.create_pvp(X)

    with pytest.raises(DomainError):
        session.setup_match(X)


def test_setup_match_rejects_empty_player() -> None:
    session = GameSession.create_pvp(X)

    with pytest.raises(DomainError):
        session.setup_match("")


def test_setup_match_rejects_full_waiting_session() -> None:
    session = GameSession.restore(
        id="game",
        board=PlayingBoard.create_empty(),
        player_x_id=X,
        player_o_id=O,
        status=GameSessionState.WAITING,
    )

    with pytest.raises(DomainError):
        session.setup_match("third-player")


def test_turn_transitions_between_players() -> None:
    session = ready_pvp()

    session.make_move(0, 0, X)
    assert session.status == GameSessionState.TURN_O
    assert session.current_player_id == O
    assert session.get_current_turn_sign() == CellState.SIGN_O

    session.make_move(1, 1, O)
    assert session.status == GameSessionState.TURN_X
    assert session.current_player_id == X
    assert session.get_current_turn_sign() == CellState.SIGN_X


def test_waiting_session_has_no_current_player() -> None:
    session = GameSession.create_pvp(X)

    assert session.current_player_id is None
    with pytest.raises(DomainError):
        session.get_current_player_id()
    with pytest.raises(DomainError):
        session.get_current_turn_sign()


def test_make_move_rejects_waiting_session() -> None:
    session = GameSession.create_pvp(X)

    with pytest.raises(DomainError):
        session.make_move(0, 0, X)


def test_make_move_rejects_wrong_turn() -> None:
    session = ready_pvp()

    with pytest.raises(DomainError):
        session.make_move(0, 0, O)

    assert session.board.grid[0] == CellState.EMPTY


def test_make_move_rejects_non_participant() -> None:
    session = ready_pvp()

    with pytest.raises(DomainError):
        session.make_move(0, 0, "stranger")

    assert session.board.grid[0] == CellState.EMPTY


def test_make_move_rejects_out_of_bounds() -> None:
    session = ready_pvp()

    with pytest.raises(DomainError):
        session.make_move(-1, 0, X)


def test_make_move_rejects_occupied_cell() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)

    with pytest.raises(DomainError):
        session.make_move(0, 0, O)


def test_x_wins_row() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)
    session.make_move(1, 0, O)
    session.make_move(0, 1, X)
    session.make_move(1, 1, O)
    session.make_move(0, 2, X)

    assert session.status == GameSessionState.WON_X
    assert session.winner == CellState.SIGN_X
    assert session.is_finished() is True
    assert session.current_player_id is None


def test_o_wins_column() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)
    session.make_move(0, 1, O)
    session.make_move(2, 0, X)
    session.make_move(1, 1, O)
    session.make_move(2, 2, X)
    session.make_move(2, 1, O)

    assert session.status == GameSessionState.WON_O
    assert session.winner == CellState.SIGN_O
    assert session.is_finished() is True


def test_draw() -> None:
    session = ready_pvp()
    moves = [
        (0, 0, X),
        (0, 1, O),
        (0, 2, X),
        (1, 1, O),
        (1, 0, X),
        (1, 2, O),
        (2, 1, X),
        (2, 0, O),
        (2, 2, X),
    ]
    for row, col, player in moves:
        session.make_move(row, col, player)

    assert session.status == GameSessionState.DRAW
    assert session.winner is None
    assert session.is_finished() is True
    assert session.board.is_full() is True


def test_move_after_finish_is_rejected() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)
    session.make_move(1, 0, O)
    session.make_move(0, 1, X)
    session.make_move(1, 1, O)
    session.make_move(0, 2, X)

    with pytest.raises(DomainError):
        session.make_move(2, 2, O)


def test_finished_session_has_no_turn_sign() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)
    session.make_move(1, 0, O)
    session.make_move(0, 1, X)
    session.make_move(1, 1, O)
    session.make_move(0, 2, X)

    with pytest.raises(DomainError):
        session.get_current_turn_sign()


def test_resign_by_x_gives_win_to_o() -> None:
    session = ready_pvp()

    session.resign(X)

    assert session.status == GameSessionState.WON_O
    assert session.winner == CellState.SIGN_O


def test_resign_by_o_gives_win_to_x() -> None:
    session = ready_pvp()

    session.resign(O)

    assert session.status == GameSessionState.WON_X
    assert session.winner == CellState.SIGN_X


def test_resign_rejects_non_participant() -> None:
    session = ready_pvp()

    with pytest.raises(DomainError):
        session.resign("stranger")


def test_resign_rejects_waiting_session() -> None:
    session = GameSession.create_pvp(X)

    with pytest.raises(DomainError):
        session.resign(X)


def test_resign_after_finish_is_noop() -> None:
    session = ready_pvp()
    session.make_move(0, 0, X)
    session.make_move(1, 0, O)
    session.make_move(0, 1, X)
    session.make_move(1, 1, O)
    session.make_move(0, 2, X)

    session.resign(O)

    assert session.status == GameSessionState.WON_X


def test_is_participant() -> None:
    session = ready_pvp()

    assert session.is_participant(X) is True
    assert session.is_participant(O) is True
    assert session.is_participant("stranger") is False
    assert session.is_participant("") is False


def test_pve_bot_can_make_turn() -> None:
    session = GameSession.create_pve(X)

    session.make_move(0, 0, X)
    assert session.status == GameSessionState.TURN_O
    assert session.current_player_id == BOT_PLAYER_ID
    assert session.get_current_turn_sign() == CellState.SIGN_O

    session.make_move(1, 1, BOT_PLAYER_ID)
    assert session.status == GameSessionState.TURN_X
    assert session.current_player_id == X


def test_pve_resign_by_human_gives_win_to_bot() -> None:
    session = GameSession.create_pve(X)

    session.resign(X)

    assert session.status == GameSessionState.WON_O
    assert session.mode == GameMode.PVE


def test_restore_keeps_state() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    board = PlayingBoard.create_empty().set_cell(0, 0, CellState.SIGN_X)

    session = GameSession.restore(
        id="game-id",
        board=board,
        player_x_id=X,
        player_o_id=O,
        status=GameSessionState.TURN_O,
        created_at=created_at,
    )

    assert session.id == "game-id"
    assert session.board is board
    assert session.player_x_id == X
    assert session.player_o_id == O
    assert session.status == GameSessionState.TURN_O
    assert session.created_at == created_at
    assert session.mode == GameMode.PVP
