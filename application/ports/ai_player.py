from abc import ABC, abstractmethod

from domain.entities.playing_board import CellState, PlayingBoard


class AIPlayerInterface(ABC):
    @abstractmethod
    def calculate_best_move(
        self, board: PlayingBoard, ai_sign: CellState
    ) -> tuple[int, int]: ...
