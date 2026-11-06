from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import IntEnum

from domain.errors import DomainError


class CellState(IntEnum):
    EMPTY = 0
    SIGN_X = 1
    SIGN_O = 2


@dataclass(frozen=True)
class PlayingBoard:
    grid_size: int
    grid: tuple[CellState, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.grid_size <= 0:
            raise DomainError("Размер сетки должен быть больше 0")
        if len(self.grid) != self.grid_size * self.grid_size:
            raise DomainError("Длина сетки не соответствует её размеру")
        if not all(isinstance(cell, CellState) for cell in self.grid):
            raise DomainError("Сетка должна состоять только из CellState")

    @classmethod
    def create_empty(cls, grid_size: int = 3) -> "PlayingBoard":
        empty_grid = (CellState.EMPTY,) * (grid_size * grid_size)
        return cls(grid_size=grid_size, grid=empty_grid)

    @classmethod
    def from_int_list(
        cls, grid_cells: Sequence[int], grid_size: int = 3
    ) -> "PlayingBoard":
        if len(grid_cells) != grid_size * grid_size:
            raise DomainError("Длина списка не соответствует размеру сетки")

        try:
            grid = tuple(CellState(value) for value in grid_cells)
        except (TypeError, ValueError) as exc:
            raise DomainError("Некорректное значение клетки доски") from exc

        return cls(grid_size=grid_size, grid=grid)

    def to_int_list(self) -> list[int]:
        return [cell.value for cell in self.grid]

    def set_cell(self, row: int, col: int, state: CellState) -> "PlayingBoard":
        size = self.grid_size
        if not (0 <= row < size and 0 <= col < size):
            raise DomainError(f"Координаты [{row}:{col}] выходят за границы доски!")

        try:
            sign = CellState(state)
        except (TypeError, ValueError) as exc:
            raise DomainError("Некорректное состояние клетки доски") from exc

        if sign not in (CellState.SIGN_X, CellState.SIGN_O):
            raise DomainError("В клетку можно поставить только X или O")

        idx = row * size + col
        if self.grid[idx] != CellState.EMPTY:
            raise DomainError(f"Клетка {row}:{col} уже занята!")

        new_grid = list(self.grid)
        new_grid[idx] = sign

        return PlayingBoard(grid_size=self.grid_size, grid=tuple(new_grid))

    def is_full(self) -> bool:
        return all(cell != CellState.EMPTY for cell in self.grid)

    def get_empty_cells(self) -> list[tuple[int, int]]:
        return [
            (idx // self.grid_size, idx % self.grid_size)
            for idx, cell in enumerate(self.grid)
            if cell == CellState.EMPTY
        ]

    def iter_lines(self) -> Iterator[list[CellState]]:
        size = self.grid_size

        for row in range(size):
            yield [self.grid[row * size + col] for col in range(size)]

        for col in range(size):
            yield [self.grid[row * size + col] for row in range(size)]

        for offset in range(-size + 1, size):
            yield [
                self.grid[row * size + col]
                for row in range(size)
                for col in range(size)
                if row - col == offset
            ]

        for offset in range(2 * size - 1):
            yield [
                self.grid[row * size + col]
                for row in range(size)
                for col in range(size)
                if row + col == offset
            ]
