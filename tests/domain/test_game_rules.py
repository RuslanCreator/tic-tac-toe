from domain.entities.game_session import GameRules
from domain.entities.playing_board import CellState, PlayingBoard

_EMPTY = CellState.EMPTY.value
_X = CellState.SIGN_X.value
_O = CellState.SIGN_O.value


def board_from_rows(rows: list[str]) -> PlayingBoard:
    mapping = {" ": _EMPTY, "X": _X, "O": _O}
    cells = [mapping[char] for row in rows for char in row]
    return PlayingBoard.from_int_list(cells, grid_size=len(rows))


def test_empty_board_has_no_winner() -> None:
    board = PlayingBoard.create_empty()

    assert GameRules.get_winner(board) == CellState.EMPTY


def test_row_win() -> None:
    board = board_from_rows(["XXX", "OO ", "   "])

    assert GameRules.get_winner(board) == CellState.SIGN_X


def test_column_win() -> None:
    board = board_from_rows(["XOO", "X  ", "X  "])

    assert GameRules.get_winner(board) == CellState.SIGN_X


def test_main_diagonal_win() -> None:
    board = board_from_rows(["XOO", " X ", "  X"])

    assert GameRules.get_winner(board) == CellState.SIGN_X


def test_anti_diagonal_win() -> None:
    board = board_from_rows(["  O", " O ", "O  "])

    assert GameRules.get_winner(board) == CellState.SIGN_O


def test_short_diagonal_does_not_count_as_win() -> None:
    board = board_from_rows(["X  ", " X ", "   "])

    assert GameRules.get_winner(board) == CellState.EMPTY


def test_draw_has_no_winner() -> None:
    board = board_from_rows(["XOX", "XOO", "OXX"])

    assert GameRules.get_winner(board) == CellState.EMPTY


def test_win_on_larger_board() -> None:
    board = board_from_rows(["XXXX", "OOOO", "    ", "    "])

    assert GameRules.get_winner(board) == CellState.SIGN_X
