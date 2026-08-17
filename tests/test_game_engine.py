from __future__ import annotations

import pytest

from ur_tictactoe.game.engine import Board, O, X


def board_with_moves(*moves: tuple[int, str]) -> Board:
    board = Board()
    for cell, player in moves:
        board.make_move(cell, player)
    return board


def test_empty_board() -> None:
    board = Board()
    assert board.cells == (None,) * 9
    assert board.winner() is None


def test_cells_use_public_numbers_one_through_nine() -> None:
    board = Board()
    for cell in range(1, 10):
        assert board.cell(cell) is None
    with pytest.raises(ValueError):
        board.cell(0)


def test_valid_move() -> None:
    board = Board()
    board.make_move(5, X)
    assert board.cell(5) == X


def test_rejects_occupied_cell() -> None:
    board = board_with_moves((5, X))
    with pytest.raises(ValueError, match="occupied"):
        board.make_move(5, O)


@pytest.mark.parametrize("cell", [0, 10, -1, True])
def test_rejects_cell_outside_public_range(cell: int) -> None:
    with pytest.raises(ValueError, match="1 to 9"):
        Board().make_move(cell, X)


def test_available_moves() -> None:
    board = board_with_moves((1, X), (5, O), (9, X))
    assert board.available_moves() == [2, 3, 4, 6, 7, 8]


def test_horizontal_win() -> None:
    assert board_with_moves((1, X), (4, O), (2, X), (5, O), (3, X)).winner() == X


def test_vertical_win() -> None:
    assert board_with_moves((1, O), (2, X), (4, O), (3, X), (7, O)).winner() == O


def test_diagonal_win() -> None:
    assert board_with_moves((1, X), (2, O), (5, X), (3, O), (9, X)).winner() == X


def test_draw() -> None:
    board = board_with_moves(
        (1, X), (2, O), (3, X), (4, X), (5, O), (6, O), (7, O), (8, X), (9, X)
    )
    assert board.is_draw()


def test_game_over_for_win_and_draw() -> None:
    win = board_with_moves((1, X), (4, O), (2, X), (5, O), (3, X))
    draw = Board((X, O, X, X, O, O, O, X, X))
    assert win.is_game_over()
    assert draw.is_game_over()
    assert not Board().is_game_over()
