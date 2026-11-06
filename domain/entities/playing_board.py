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

    @classmethod
    def create_empty(cls, grid_size: int = 3) -> "PlayingBoard":
        if grid_size <= 0:
            raise DomainError("Размер сетки должен быть больше 0")
        empty_grid = (CellState.EMPTY,) * (grid_size * grid_size)
        return cls(grid_size=grid_size, grid=empty_grid)

    @classmethod
    def from_int_list(cls, grid_cells: list[int], grid_size: int = 3) -> "PlayingBoard":
        if grid_size <= 0:
            raise DomainError("Размер сетки должен быть больше 0")
        if len(grid_cells) != grid_size * grid_size:
            raise DomainError("Длина списка не соответствует размеру сетки")

        return cls(
            grid_size=grid_size, grid=tuple(CellState(val) for val in grid_cells)
        )

    def to_int_list(self) -> list[int]:
        return [cell.value for cell in self.grid]

    def set_cell(self, row: int, col: int, state: CellState) -> "PlayingBoard":
        size = self.grid_size
        if not (0 <= row < size and 0 <= col < size):
            raise DomainError(f"Координаты [{row}:{col}] выходят за границы доски!")

        idx = row * size + col
        if self.grid[idx] != CellState.EMPTY:
            raise DomainError(f"Клетка {row}:{col} уже занята!")

        new_grid = list(self.grid)
        new_grid[idx] = state

        return PlayingBoard(grid_size=self.grid_size, grid=tuple(new_grid))

    def is_full(self) -> bool:
        return all(cell != CellState.EMPTY for cell in self.grid)

    def get_empty_cells(self) -> list[tuple[int, int]]:
        return [
            (idx // self.grid_size, idx % self.grid_size)
            for idx, cell in enumerate(self.grid)
            if cell == CellState.EMPTY
        ]

    def iter_lines(self) -> "...":
        size = self.grid_size
        for r in range(size):
            yield [self.grid[r * size + c] for c in range(size)]

        for c in range(size):
            yield [self.grid[c + r * size] for r in range(size)]

        for d in range(-size + 1, size):
            yield [
                self.grid[r * size + c]
                for r in range(size)
                for c in range(size)
                if r - c == d
            ]

        for d in range(0, 2 * size - 1):
            yield [
                self.grid[r * size + c]
                for r in range(size)
                for c in range(size)
                if r + c == d
            ]
