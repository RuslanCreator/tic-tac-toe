import hashlib
import hmac
import secrets

from application.ports.ai_player import AIPlayerInterface
from application.ports.password_hasher import PasswordHasherInterface
from domain.entities.game_session import GameRules
from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError


class PasswordCryptoService(PasswordHasherInterface):
    """PBKDF2-SHA256 со случайной солью на каждый пароль.

    Старый формат (один общий статический salt) поддерживается только для
    чтения, чтобы существующие пользователи могли войти после обновления.
    """

    _ALGORITHM = "pbkdf2_sha256"
    _ITERATIONS = 600_000
    _SALT_BYTES = 16
    _MAX_ITERATIONS = 2_000_000

    _LEGACY_SALT = b"secret_salt_1"
    _LEGACY_ITERATIONS = 100_000

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(self._SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, self._ITERATIONS
        )
        return f"{self._ALGORITHM}${self._ITERATIONS}${salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith(f"{self._ALGORITHM}$"):
            return self._verify_current_format(password, password_hash)
        return self._verify_legacy_format(password, password_hash)

    def _verify_current_format(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations_raw, salt_hex, digest_hex = password_hash.split(
                "$", 3
            )
            iterations = int(iterations_raw)
            salt = bytes.fromhex(salt_hex)
            expected_digest = bytes.fromhex(digest_hex)
        except (TypeError, ValueError):
            return False

        if algorithm != self._ALGORITHM:
            return False
        if not 1 <= iterations <= self._MAX_ITERATIONS:
            return False

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, iterations
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    def _verify_legacy_format(self, password: str, password_hash: str) -> bool:
        legacy_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            self._LEGACY_SALT,
            self._LEGACY_ITERATIONS,
        ).hex()
        return hmac.compare_digest(legacy_digest.encode(), password_hash.encode())


class MiniMaxService(AIPlayerInterface):
    def calculate_best_move(
        self, board: PlayingBoard, ai_sign: CellState
    ) -> tuple[int, int]:
        empty_cells = board.get_empty_cells()
        if not empty_cells:
            raise DomainError("Нет доступных клеток для хода ИИ!")

        if len(empty_cells) == board.grid_size * board.grid_size:
            return (board.grid_size // 2, board.grid_size // 2)

        human_sign = (
            CellState.SIGN_O if ai_sign == CellState.SIGN_X else CellState.SIGN_X
        )
        max_score = board.grid_size * board.grid_size + 1

        best_score = float("-inf")
        best_move = empty_cells[0]

        for row, col in empty_cells:
            simulated_board = board.set_cell(row, col, ai_sign)
            score = self._minimax(
                board=simulated_board,
                depth=0,
                is_maximizing=False,
                ai_sign=ai_sign,
                human_sign=human_sign,
                max_score=max_score,
            )

            if score > best_score:
                best_score = score
                best_move = (row, col)

        return best_move

    def _minimax(
        self,
        board: PlayingBoard,
        depth: int,
        is_maximizing: bool,
        ai_sign: CellState,
        human_sign: CellState,
        max_score: int,
    ) -> int:
        winner = GameRules.get_winner(board)
        if winner == ai_sign:
            return max_score - depth
        if winner == human_sign:
            return depth - max_score
        if board.is_full():
            return 0

        empty_cells = board.get_empty_cells()

        if is_maximizing:
            max_eval = float("-inf")
            for row, col in empty_cells:
                simulated_board = board.set_cell(row, col, ai_sign)
                evaluation = self._minimax(
                    board=simulated_board,
                    depth=depth + 1,
                    is_maximizing=False,
                    ai_sign=ai_sign,
                    human_sign=human_sign,
                    max_score=max_score,
                )
                max_eval = max(max_eval, evaluation)
            return max_eval

        else:
            min_eval = float("inf")
            for row, col in empty_cells:
                simulated_board = board.set_cell(row, col, human_sign)
                evaluation = self._minimax(
                    board=simulated_board,
                    depth=depth + 1,
                    is_maximizing=True,
                    ai_sign=ai_sign,
                    human_sign=human_sign,
                    max_score=max_score,
                )
                min_eval = min(min_eval, evaluation)
            return min_eval
