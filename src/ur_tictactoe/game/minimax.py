"""Full-depth Minimax for the 3x3 game."""

from __future__ import annotations

import random
from functools import lru_cache

from ur_tictactoe.game.engine import Board, O, PLAYERS, WINNING_LINES, X

CORNERS = (1, 3, 7, 9)
HARD = "hard"
INTERMEDIATE = "intermediate"
INTERMEDIATE_DEPTH = 2


def _other_player(player: str) -> str:
    if player not in PLAYERS:
        raise ValueError("Player must be X or O")
    return O if player == X else X


def _score(board: Board, turn: str, robot: str, human: str, depth: int) -> int:
    return _cached_score(board.cells, turn, robot, human, depth)


@lru_cache(maxsize=None)
def _cached_score(
    cells: tuple[str | None, ...], turn: str, robot: str, human: str, depth: int
) -> int:
    board = Board(cells)
    winner = board.winner()
    if winner == robot:
        return 10 - depth
    if winner == human:
        return depth - 10
    if board.is_draw():
        return 0

    scores: list[int] = []
    for move in board.available_moves():
        candidate = board.copy()
        candidate.make_move(move, turn)
        scores.append(_score(candidate, _other_player(turn), robot, human, depth + 1))
    return max(scores) if turn == robot else min(scores)


def _move_score(board: Board, move: int, robot: str, human: str) -> int:
    candidate = board.copy()
    candidate.make_move(move, robot)
    return _score(candidate, human, robot, human, 1)


def count_optimal_human_responses(board: Board, robot: str, human: str) -> int:
    """Count human replies that preserve the human's best Minimax outcome.

    A lower count means the human has fewer equally correct replies. This is used
    only after the primary Minimax value has selected mathematically safe moves.
    """
    if board.is_game_over():
        return 0

    scores: list[int] = []
    for move in board.available_moves():
        candidate = board.copy()
        candidate.make_move(move, human)
        scores.append(_score(candidate, robot, robot, human, 1))
    best_human_score = min(scores)
    return scores.count(best_human_score)


def best_move(
    board: Board,
    robot: str,
    human: str | None = None,
    seed: int | None = None,
) -> int | None:
    """Return an optimal robot move, or None when the board is terminal."""
    if robot not in PLAYERS:
        raise ValueError("Robot must be X or O")
    human = _other_player(robot) if human is None else human
    if human not in PLAYERS or human == robot:
        raise ValueError("Human and robot must use different X/O marks")
    if board.is_game_over():
        return None

    moves = board.available_moves()
    if len(moves) == 9:
        return random.Random(seed).choice(CORNERS)

    scored_moves = [(move, _move_score(board, move, robot, human)) for move in moves]
    optimal_score = max(score for _, score in scored_moves)
    optimal_moves = [move for move, score in scored_moves if score == optimal_score]

    def aggressive_score(move: int) -> int:
        candidate = board.copy()
        candidate.make_move(move, robot)
        return count_optimal_human_responses(candidate, robot, human)

    return min(optimal_moves, key=lambda move: (aggressive_score(move), move))


def _immediate_move(board: Board, player: str) -> int | None:
    for move in board.available_moves():
        candidate = board.copy()
        candidate.make_move(move, player)
        if candidate.winner() == player:
            return move
    return None


def _heuristic(board: Board, robot: str, human: str) -> int:
    """Estimate a non-terminal board using open lines and useful positions."""
    score = 0
    for line in WINNING_LINES:
        values = [board.cell(cell) for cell in line]
        robot_count = values.count(robot)
        human_count = values.count(human)
        if human_count == 0:
            score += (0, 1, 3, 0)[robot_count]
        if robot_count == 0:
            score -= (0, 1, 3, 0)[human_count]

    if board.cell(5) == robot:
        score += 2
    elif board.cell(5) == human:
        score -= 2
    score += sum(board.cell(cell) == robot for cell in CORNERS)
    score -= sum(board.cell(cell) == human for cell in CORNERS)
    return score


def _limited_score(
    board: Board,
    turn: str,
    robot: str,
    human: str,
    depth: int,
    depth_limit: int,
) -> int:
    winner = board.winner()
    if winner == robot:
        return 100 - depth
    if winner == human:
        return depth - 100
    if board.is_draw():
        return 0
    if depth >= depth_limit:
        return _heuristic(board, robot, human)

    scores: list[int] = []
    for move in board.available_moves():
        candidate = board.copy()
        candidate.make_move(move, turn)
        scores.append(
            _limited_score(
                candidate,
                _other_player(turn),
                robot,
                human,
                depth + 1,
                depth_limit,
            )
        )
    return max(scores) if turn == robot else min(scores)


def intermediate_move(
    board: Board,
    robot: str,
    human: str | None = None,
    seed: int | None = None,
) -> int | None:
    """Choose a reasonable move with a two-ply, depth-limited search."""
    if robot not in PLAYERS:
        raise ValueError("Robot must be X or O")
    human = _other_player(robot) if human is None else human
    if human not in PLAYERS or human == robot:
        raise ValueError("Human and robot must use different X/O marks")
    if board.is_game_over():
        return None

    winning_move = _immediate_move(board, robot)
    if winning_move is not None:
        return winning_move
    blocking_move = _immediate_move(board, human)
    if blocking_move is not None:
        return blocking_move

    moves = board.available_moves()
    if len(moves) == 9:
        return random.Random(seed).choice(CORNERS)

    scores: list[tuple[int, int]] = []
    for move in moves:
        candidate = board.copy()
        candidate.make_move(move, robot)
        score = _limited_score(
            candidate, human, robot, human, 1, INTERMEDIATE_DEPTH
        )
        scores.append((move, score))
    return max(scores, key=lambda item: (item[1], -item[0]))[0]


def choose_move(
    board: Board,
    robot: str,
    human: str | None = None,
    difficulty: str = HARD,
    seed: int | None = None,
) -> int | None:
    """Choose a robot move using exactly one of the two supported levels."""
    if difficulty == HARD:
        return best_move(board, robot, human, seed)
    if difficulty == INTERMEDIATE:
        return intermediate_move(board, robot, human, seed)
    raise ValueError(f"Unknown difficulty: {difficulty}")
