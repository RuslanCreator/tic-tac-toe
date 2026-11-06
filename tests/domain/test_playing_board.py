import pytest

from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError


def test_create_empty_builds_square_board() -> None:
    board = PlayingBoard.create_empty()

    assert board.grid_size == 3
    assert len(board.grid) == 9
    assert all(cell == CellState.EMPTY for cell in board.grid)
    assert board.to_int_list() == [0] * 9


def test_create_empty_rejects_non_positive_size() -> None:
    with pytest.raises(DomainError):
        PlayingBoard.create_empty(grid_size=0)
    with pytest.raises(DomainError):
        PlayingBoard.create_empty(grid_size=-1)


def test_from_int_list_roundtrip() -> None:
    values = [0, 1, 2, 0, 1, 2, 0, 1, 2]
    board = PlayingBoard.from_int_list(values)

    assert board.to_int_list() == values
    assert board.grid[1] == CellState.SIGN_X
    assert board.grid[2] == CellState.SIGN_O


def test_from_int_list_rejects_wrong_length() -> None:
    with pytest.raises(DomainError):
        PlayingBoard.from_int_list([0, 1], grid_size=3)


def test_from_int_list_rejects_unknown_cell_value() -> None:
    with pytest.raises(DomainError):
        PlayingBoard.from_int_list([9, 0, 0, 0, 0, 0, 0, 0, 0])


def test_direct_construction_validates_grid_length() -> None:
    with pytest.raises(DomainError):
        PlayingBoard(grid_size=3, grid=(CellState.EMPTY,))


def test_direct_construction_rejects_plain_ints() -> None:
    with pytest.raises(DomainError):
        PlayingBoard(grid_size=3, grid=(0, 0, 0, 0, 0, 0, 0, 0, 0))  # type: ignore[arg-type]


def test_set_cell_returns_new_board() -> None:
    board = PlayingBoard.create_empty()
    updated = board.set_cell(1, 2, CellState.SIGN_X)

    assert updated.grid[1 * 3 + 2] == CellState.SIGN_X
    assert board.grid[1 * 3 + 2] == CellState.EMPTY
    assert board is not updated


@pytest.mark.parametrize(
    ("row", "col"),
    [(-1, 0), (0, -1), (3, 0), (0, 3)],
)
def test_set_cell_rejects_out_of_bounds(row: int, col: int) -> None:
    board = PlayingBoard.create_empty()

    with pytest.raises(DomainError):
        board.set_cell(row, col, CellState.SIGN_X)


def test_set_cell_rejects_occupied_cell() -> None:
    board = PlayingBoard.create_empty().set_cell(0, 0, CellState.SIGN_X)

    with pytest.raises(DomainError):
        board.set_cell(0, 0, CellState.SIGN_O)


def test_set_cell_rejects_empty_sign() -> None:
    board = PlayingBoard.create_empty()

    with pytest.raises(DomainError):
        board.set_cell(0, 0, CellState.EMPTY)


def test_is_full_and_empty_cells() -> None:
    board = PlayingBoard.from_int_list([1, 2, 1, 2, 1, 2, 2, 1, 2])

    assert board.is_full() is True
    assert board.get_empty_cells() == []

    empty_board = PlayingBoard.create_empty()
    assert empty_board.is_full() is False
    assert empty_board.get_empty_cells() == [
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (1, 2),
        (2, 0),
        (2, 1),
        (2, 2),
    ]
