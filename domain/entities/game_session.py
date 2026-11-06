import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from domain.errors import DomainError

from .player import BOT_PLAYER_ID
from .playing_board import CellState, PlayingBoard


class GameRules:
    @staticmethod
    def get_winner(board: PlayingBoard) -> CellState:
        for line in board.iter_lines():
            if len(line) != board.grid_size:
                continue

            first_cell = line[0]
            if first_cell != CellState.EMPTY and all(
                cell == first_cell for cell in line
            ):
                return first_cell

        return CellState.EMPTY


class GameSessionState(StrEnum):
    WAITING = "WAITING"
    TURN_X = "TURN_X"
    TURN_O = "TURN_O"
    DRAW = "DRAW"
    WON_X = "WON_X"
    WON_O = "WON_O"


class GameMode(StrEnum):
    PVP = "PVP"
    PVE = "PVE"


@dataclass(kw_only=True)
class GameSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    board: PlayingBoard = field(default_factory=PlayingBoard.create_empty)
    player_x_id: str | None = None
    player_o_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _status: GameSessionState = GameSessionState.WAITING

    @property
    def status(self) -> GameSessionState:
        return self._status

    @property
    def mode(self) -> GameMode:
        if self.player_o_id == BOT_PLAYER_ID:
            return GameMode.PVE
        return GameMode.PVP

    @property
    def is_pve(self) -> bool:
        return self.mode == GameMode.PVE

    @property
    def is_waiting(self) -> bool:
        return self._status == GameSessionState.WAITING

    @property
    def current_player_id(self) -> str | None:
        if self._status == GameSessionState.TURN_X:
            return self.player_x_id
        if self._status == GameSessionState.TURN_O:
            return self.player_o_id
        return None

    @property
    def winner(self) -> CellState | None:
        if self._status == GameSessionState.WON_X:
            return CellState.SIGN_X
        if self._status == GameSessionState.WON_O:
            return CellState.SIGN_O
        return None

    @property
    def status_text(self) -> str:
        match self._status:
            case GameSessionState.WAITING:
                return "Waiting for players"
            case GameSessionState.DRAW:
                return "Draw"
            case GameSessionState.TURN_X:
                return f"Player’s turn with UUID {self.player_x_id}"
            case GameSessionState.TURN_O:
                return f"Player’s turn with UUID {self.player_o_id}"
            case GameSessionState.WON_X:
                return f"Victory for player with UUID {self.player_x_id}"
            case GameSessionState.WON_O:
                return f"Victory for player with UUID {self.player_o_id}"
            case _:
                return "Waiting for players"

    @classmethod
    def create_pvp(cls, player_id: str) -> "GameSession":
        if not player_id:
            raise DomainError("Не указан создатель игры")
        return cls(
            player_x_id=player_id,
            player_o_id=None,
            _status=GameSessionState.WAITING,
        )

    @classmethod
    def create_pve(cls, player_id: str) -> "GameSession":
        if not player_id:
            raise DomainError("Не указан создатель игры")
        return cls(
            player_x_id=player_id,
            player_o_id=BOT_PLAYER_ID,
            _status=GameSessionState.TURN_X,
        )

    @classmethod
    def restore(
        cls,
        id: str,
        board: PlayingBoard,
        player_x_id: str | None,
        player_o_id: str | None,
        status: GameSessionState,
        created_at: datetime | None = None,
    ) -> "GameSession":
        session = cls(
            id=id,
            board=board,
            player_x_id=player_x_id,
            player_o_id=player_o_id,
            created_at=created_at or datetime.now(UTC),
        )
        session._status = status
        return session

    def get_current_player_id(self) -> str:
        player_id = self.current_player_id
        if player_id is None:
            raise DomainError("Сейчас нет игрока, который должен ходить!")
        return player_id

    def get_current_turn_sign(self) -> CellState:
        if self._status == GameSessionState.TURN_O:
            return CellState.SIGN_O
        if self._status == GameSessionState.TURN_X:
            return CellState.SIGN_X
        raise DomainError("Сейчас не ход игрока!")

    def setup_match(self, player_id_o: str) -> None:
        if self._status != GameSessionState.WAITING:
            raise DomainError(
                "Невозможно запустить матч: сессия уже активна или завершена!"
            )

        if not self.player_x_id:
            raise DomainError("Ошибка домена: у лобби отсутствует создатель (игрок X)!")

        if not player_id_o:
            raise DomainError("Не указан второй игрок")

        if player_id_o == self.player_x_id:
            raise DomainError("Нельзя играть против самого себя")

        if self.player_o_id is not None:
            raise DomainError("В этой игровой сессии уже нет свободных мест!")

        self.player_o_id = player_id_o
        self._status = GameSessionState.TURN_X

    def make_move(self, row: int, col: int, player_id: str) -> None:
        if self._status == GameSessionState.WAITING:
            raise DomainError("Нельзя совершить ход! Игра ожидает второго игрока.")
        if self.is_finished():
            raise DomainError("Попытка сделать ход в уже завершенной игре!")
        if not self.is_participant(player_id):
            raise DomainError("Игрок не участвует в этой игре!")

        expected_player_id = self.get_current_player_id()
        if player_id != expected_player_id:
            raise DomainError("Сейчас ход другого игрока!")

        self.board = self.board.set_cell(row, col, self.get_current_turn_sign())
        winner = GameRules.get_winner(self.board)

        if winner == CellState.SIGN_X:
            self._status = GameSessionState.WON_X
        elif winner == CellState.SIGN_O:
            self._status = GameSessionState.WON_O
        elif self.board.is_full():
            self._status = GameSessionState.DRAW
        else:
            self._status = (
                GameSessionState.TURN_O
                if self._status == GameSessionState.TURN_X
                else GameSessionState.TURN_X
            )

    def resign(self, player_id: str) -> None:
        if self.is_finished():
            return
        if self._status == GameSessionState.WAITING:
            raise DomainError("Нельзя сдаться до начала игры")
        if not self.is_participant(player_id):
            raise DomainError("Игрок не участвует в этой игре!")

        if player_id == self.player_x_id:
            self._status = GameSessionState.WON_O
        else:
            self._status = GameSessionState.WON_X

    def is_finished(self) -> bool:
        return self._status in (
            GameSessionState.DRAW,
            GameSessionState.WON_X,
            GameSessionState.WON_O,
        )

    def is_participant(self, player_id: str) -> bool:
        if not player_id:
            return False
        return player_id in (self.player_x_id, self.player_o_id)
