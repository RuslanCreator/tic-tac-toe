from datetime import UTC, datetime

from domain.entities.game_session import GameSession, GameSessionState
from domain.entities.player import Player
from domain.entities.playing_board import CellState, PlayingBoard
from infrastructure.mappers.game_session import GameSessionMapper
from infrastructure.mappers.player import PlayerMapper

X = "player-x"  # noqa: E741
O = "player-o"  # noqa: E741


def test_game_session_roundtrip() -> None:
    created_at = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)
    board = PlayingBoard.create_empty()
    board = board.set_cell(0, 0, CellState.SIGN_X)
    board = board.set_cell(1, 1, CellState.SIGN_O)
    session = GameSession.restore(
        id="game-id",
        board=board,
        player_x_id=X,
        player_o_id=O,
        status=GameSessionState.TURN_X,
        created_at=created_at,
    )

    model = GameSessionMapper.to_data(session)
    restored = GameSessionMapper.to_domain(model)

    assert restored.id == "game-id"
    assert restored.player_x_id == X
    assert restored.player_o_id == O
    assert restored.status == GameSessionState.TURN_X
    assert restored.board.grid == board.grid
    assert restored.board.grid_size == 3
    assert restored.created_at == created_at


def test_game_session_update_keeps_identity() -> None:
    session = GameSession.create_pvp(X)
    model = GameSessionMapper.to_data(session)
    session.setup_match(O)
    session.make_move(0, 0, X)

    GameSessionMapper.update_data_model(session, model)

    assert model.player_o_id == O
    assert model.status == GameSessionState.TURN_O.value
    assert model.grid_cells[0] == CellState.SIGN_X.value


def test_player_roundtrip() -> None:
    player = Player(id="player-id", login="alice")

    model = PlayerMapper.to_data(player)
    restored = PlayerMapper.to_domain(model)

    assert restored == player
