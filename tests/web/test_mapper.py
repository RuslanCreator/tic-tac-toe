import uuid
from datetime import UTC, datetime

from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from domain.entities.game_session import GameSession, GameSessionState
from domain.entities.player import BOT_PLAYER_ID
from domain.entities.playing_board import CellState, PlayingBoard
from web.mapper import WebGameMapper

X = "player-x"  # noqa: E741
O = "player-o"  # noqa: E741
GAME_ID = str(uuid.uuid4())


def test_pve_game_is_mapped_with_full_state() -> None:
    session = GameSession.create_pve(X)

    response = WebGameMapper.to_web_response(session)

    assert str(response.game_session_id) == session.id
    assert response.mode.value == "PVE"
    assert response.status == GameSessionState.TURN_X
    assert response.grid_size == 3
    assert response.player_x_id == X
    assert response.player_o_id == BOT_PLAYER_ID
    assert response.current_player_id == X
    assert response.is_finished is False
    assert response.board == [""] * 9


def test_board_cells_are_mapped_to_strings() -> None:
    board = PlayingBoard.create_empty().set_cell(0, 0, CellState.SIGN_X)
    board = board.set_cell(1, 1, CellState.SIGN_O)
    session = GameSession.restore(
        id=GAME_ID,
        board=board,
        player_x_id=X,
        player_o_id=O,
        status=GameSessionState.TURN_X,
    )

    response = WebGameMapper.to_web_response(session)

    assert response.board[0] == "X"
    assert response.board[4] == "O"
    assert response.board[1] == ""


def test_finished_game_is_marked_finished() -> None:
    board = PlayingBoard.from_int_list([1, 1, 1, 2, 2, 0, 0, 0, 0])
    session = GameSession.restore(
        id=GAME_ID,
        board=board,
        player_x_id=X,
        player_o_id=O,
        status=GameSessionState.WON_X,
    )

    response = WebGameMapper.to_web_response(session)

    assert response.is_finished is True
    assert response.current_player_id is None


def test_waiting_sessions_are_mapped() -> None:
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    sessions = [
        WaitingSessionInfo(game_session_id=first_id, creator_login="alice"),
        WaitingSessionInfo(game_session_id=second_id, creator_login="bob"),
    ]

    response = WebGameMapper.to_available_sessions_response(sessions)

    assert [item.creator_login for item in response.sessions] == ["alice", "bob"]
    assert str(response.sessions[0].game_session_id) == first_id


def test_finished_sessions_are_mapped() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    game_id = str(uuid.uuid4())
    infos = [
        FinishedSessionInfo(
            game_session_id=game_id,
            status=GameSessionState.WON_X,
            result="WIN",
            created_at=created_at,
        )
    ]

    response = WebGameMapper.to_finished_sessions_response(infos)

    assert response.sessions[0].result == "WIN"
    assert response.sessions[0].created_at == created_at
    assert str(response.sessions[0].game_session_id) == game_id
