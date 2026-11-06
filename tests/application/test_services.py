import hashlib

import pytest

from application.services import MiniMaxService, PasswordCryptoService
from domain.entities.playing_board import CellState, PlayingBoard
from domain.errors import DomainError


def test_hash_is_salted_and_verifiable() -> None:
    service = PasswordCryptoService()

    first = service.hash_password("secret")
    second = service.hash_password("secret")

    assert first != second
    assert first.startswith("pbkdf2_sha256$")
    assert service.verify_password("secret", first) is True
    assert service.verify_password("secret", second) is True


def test_wrong_password_is_rejected() -> None:
    service = PasswordCryptoService()
    password_hash = service.hash_password("secret")

    assert service.verify_password("wrong", password_hash) is False


def test_legacy_hash_is_still_supported() -> None:
    service = PasswordCryptoService()
    # Считаем legacy-хеш тем же алгоритмом, что использовался раньше.
    legacy_hash = hashlib.pbkdf2_hmac(
        "sha256",
        b"secret",
        service._LEGACY_SALT,
        service._LEGACY_ITERATIONS,
    ).hex()

    assert service.verify_password("secret", legacy_hash) is True
    assert service.verify_password("wrong", legacy_hash) is False


def test_malformed_hash_is_rejected() -> None:
    service = PasswordCryptoService()

    assert service.verify_password("secret", "pbkdf2_sha256$broken") is False
    assert service.verify_password("secret", "pbkdf2_sha256$abc$00$00") is False


def test_minimax_takes_immediate_win() -> None:
    service = MiniMaxService()
    board = PlayingBoard.from_int_list([2, 2, 0, 1, 1, 0, 0, 0, 0])

    assert service.calculate_best_move(board, CellState.SIGN_O) == (0, 2)


def test_minimax_blocks_immediate_loss() -> None:
    service = MiniMaxService()
    board = PlayingBoard.from_int_list([1, 1, 0, 0, 2, 0, 0, 0, 0])

    assert service.calculate_best_move(board, CellState.SIGN_O) == (0, 2)


def test_minimax_starts_from_center_on_empty_board() -> None:
    service = MiniMaxService()

    assert service.calculate_best_move(
        PlayingBoard.create_empty(), CellState.SIGN_O
    ) == (1, 1)


def test_minimax_requires_empty_cell() -> None:
    service = MiniMaxService()
    board = PlayingBoard.from_int_list([1, 2, 1, 2, 1, 2, 2, 1, 2])

    with pytest.raises(DomainError):
        service.calculate_best_move(board, CellState.SIGN_O)
