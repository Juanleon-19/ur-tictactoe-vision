from __future__ import annotations

from ur_tictactoe.game.engine import Board, O, X
from ur_tictactoe.game.minimax import best_move, count_optimal_human_responses


def board_with_moves(*moves: tuple[int, str]) -> Board:
    board = Board()
    for cell, player in moves:
        board.make_move(cell, player)
    return board


def test_takes_immediate_win() -> None:
    board = board_with_moves((1, X), (4, O), (2, X), (5, O))
    assert best_move(board, X, O) == 3


def test_blocks_immediate_human_win() -> None:
    board = board_with_moves((1, O), (5, X), (2, O))
    assert best_move(board, X, O) == 3


def test_never_returns_occupied_cell() -> None:
    board = board_with_moves((1, X), (5, O), (9, X))
    assert best_move(board, O, X) in board.available_moves()


def test_does_not_modify_original_board() -> None:
    board = board_with_moves((1, X), (5, O))
    original = board.cells
    best_move(board, X, O)
    assert board.cells == original


def test_terminal_state_has_no_move() -> None:
    board = board_with_moves((1, X), (4, O), (2, X), (5, O), (3, X))
    assert best_move(board, O, X) is None


def test_prefers_faster_win() -> None:
    board = Board((X, O, None, None, X, O, None, None, None))
    assert best_move(board, X, O) == 9


def test_robot_opening_is_seeded_random_corner() -> None:
    openings = {best_move(Board(), X, O, seed) for seed in range(20)}
    assert openings <= {1, 3, 7, 9}
    assert len(openings) > 1
    assert best_move(Board(), X, O, 42) == best_move(Board(), X, O, 42)


def test_aggressive_tie_break_helper_is_small_and_non_mutating() -> None:
    board = board_with_moves((1, X))
    original = board.cells
    count = count_optimal_human_responses(board, X, O)
    assert count >= 1
    assert board.cells == original


def _explore_human_replies(
    board: Board, turn: str, robot: str, human: str
) -> tuple[int, int, int]:
    if board.is_game_over():
        winner = board.winner()
        return (int(winner == robot), int(winner == human), int(winner is None))

    if turn == robot:
        move = best_move(board, robot, human, seed=42)
        assert move in board.available_moves()
        next_board = board.copy()
        next_board.make_move(move, robot)
        return _explore_human_replies(next_board, human, robot, human)

    totals = [0, 0, 0]
    for move in board.available_moves():
        next_board = board.copy()
        next_board.make_move(move, human)
        result = _explore_human_replies(next_board, robot, robot, human)
        totals = [left + right for left, right in zip(totals, result)]
    return tuple(totals)  # type: ignore[return-value]


def test_robot_cannot_lose_when_robot_starts() -> None:
    robot_wins, human_wins, draws = _explore_human_replies(Board(), X, X, O)
    assert human_wins == 0
    assert robot_wins + draws > 0


def test_robot_cannot_lose_when_human_starts() -> None:
    robot_wins, human_wins, draws = _explore_human_replies(Board(), X, O, X)
    assert human_wins == 0
    assert robot_wins + draws > 0


def test_exploits_known_human_error_with_forced_win() -> None:
    board = board_with_moves((1, X), (2, O), (5, X), (9, O))
    assert best_move(board, X, O) in {4, 7}
    robot_wins, human_wins, draws = _explore_human_replies(board, X, X, O)
    assert robot_wins > 0
    assert human_wins == draws == 0


def test_selects_winning_line_instead_of_available_draw() -> None:
    board = Board((X, O, X, O, X, None, None, None, O))
    assert best_move(board, X, O) == 7


def test_automatic_game_reaches_a_real_terminal_state() -> None:
    board = Board()
    turn = X
    while not board.is_game_over():
        move = best_move(board, turn, O if turn == X else X, seed=7)
        assert move is not None
        board.make_move(move, turn)
        turn = O if turn == X else X
    assert board.winner() in (X, O) or board.is_draw()
