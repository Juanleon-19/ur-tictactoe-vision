from __future__ import annotations

import pytest

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.game import (
    ACTIVE,
    DRAW,
    HARD,
    HUMAN,
    HUMAN_WINS,
    INTERMEDIATE,
    ROBOT,
    ROBOT_WINS,
    GameSession,
    O,
    X,
)
from ur_tictactoe.vision.move_detector import HumanMoveDetector


def confirm_robot_turn(session: GameSession) -> int:
    move = session.request_robot_move()
    session.confirm_robot_move()
    return move


def test_empty_robot_first_session() -> None:
    session = GameSession()
    assert session.board.cells == (None,) * 9
    assert session.turn == ROBOT
    assert session.result == ACTIVE


def test_empty_human_first_session() -> None:
    session = GameSession(human_first=True)
    assert session.board.cells == (None,) * 9
    assert session.turn == HUMAN


@pytest.mark.parametrize(
    ("human_first", "human", "robot"),
    [(False, O, X), (True, X, O)],
)
def test_symbols_are_assigned_from_first_player(
    human_first: bool, human: str, robot: str
) -> None:
    session = GameSession(human_first=human_first)
    assert session.human == human
    assert session.robot == robot


def test_human_can_only_play_during_human_turn() -> None:
    with pytest.raises(ValueError, match="human's turn"):
        GameSession().play_human_move(5)


def test_human_move_updates_board_and_passes_turn() -> None:
    session = GameSession(human_first=True)
    session.play_human_move(5)
    assert session.board.cell(5) == X
    assert session.turn == ROBOT


def test_robot_can_only_decide_during_robot_turn() -> None:
    with pytest.raises(ValueError, match="robot's turn"):
        GameSession(human_first=True).request_robot_move()


def test_request_robot_move_is_legal_pending_and_does_not_change_board() -> None:
    session = GameSession(seed=42)
    original = session.board.cells
    move = session.request_robot_move()
    assert move in session.board.available_moves()
    assert session.pending_robot_move == move
    assert session.board.cells == original


def test_confirm_robot_move_updates_board_clears_pending_and_passes_turn() -> None:
    session = GameSession(seed=42)
    move = session.request_robot_move()
    session.confirm_robot_move()
    assert session.board.cell(move) == session.robot
    assert session.pending_robot_move is None
    assert session.turn == HUMAN


def test_cannot_request_twice_while_move_is_pending() -> None:
    session = GameSession()
    session.request_robot_move()
    with pytest.raises(ValueError, match="already pending"):
        session.request_robot_move()


def test_cannot_confirm_without_pending_move() -> None:
    with pytest.raises(ValueError, match="no pending"):
        GameSession().confirm_robot_move()


def test_cancel_robot_move_does_not_modify_board_and_allows_retry() -> None:
    session = GameSession(seed=42)
    original = session.board.cells
    session.request_robot_move()
    session.cancel_robot_move()
    assert session.pending_robot_move is None
    assert session.board.cells == original
    assert session.turn == ROBOT
    assert session.request_robot_move() in session.board.available_moves()


def test_human_victory_ends_session() -> None:
    session = GameSession(difficulty=INTERMEDIATE, human_first=True, seed=42)
    for human_move in (3, 7, 9):
        session.play_human_move(human_move)
        confirm_robot_turn(session)
    session.play_human_move(8)
    assert session.result == HUMAN_WINS
    assert not session.is_active
    assert session.turn is None


def test_robot_victory_ends_session() -> None:
    session = GameSession(difficulty=INTERMEDIATE, seed=42)
    for human_move in (5, 2, 4, 7):
        confirm_robot_turn(session)
        if session.is_active:
            session.play_human_move(human_move)
    confirm_robot_turn(session)
    assert session.result == ROBOT_WINS
    assert session.turn is None


def test_draw_ends_session() -> None:
    session = GameSession(difficulty=HARD, seed=42)
    for human_move in (5, 3, 4, 8):
        confirm_robot_turn(session)
        session.play_human_move(human_move)
    confirm_robot_turn(session)
    assert session.result == DRAW
    assert session.turn is None


def test_no_moves_are_accepted_after_game_over() -> None:
    session = GameSession(difficulty=INTERMEDIATE, human_first=True, seed=42)
    for human_move in (3, 7, 9):
        session.play_human_move(human_move)
        confirm_robot_turn(session)
    session.play_human_move(8)
    with pytest.raises(ValueError, match="already over"):
        session.play_human_move(2)
    with pytest.raises(ValueError, match="already over"):
        session.request_robot_move()


@pytest.mark.parametrize("difficulty", [HARD, INTERMEDIATE])
def test_session_uses_existing_difficulties(difficulty: str) -> None:
    session = GameSession(difficulty=difficulty, seed=42)
    assert session.request_robot_move() in range(1, 10)


def test_human_move_detector_connects_to_session_without_camera() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    session = GameSession(human_first=True, seed=42)
    visible = set(CELL_IDS) - {14}

    human_move = None
    for _ in range(3):
        human_move = detector.update(visible, True, set())

    assert human_move == 5
    session.play_human_move(human_move)
    robot_move = session.request_robot_move()
    assert session.pending_robot_move == robot_move
    assert session.board.cell(robot_move) is None
    session.confirm_robot_move()
    assert session.board.cell(robot_move) == session.robot
    assert session.turn == HUMAN


def test_complete_simulated_game_confirms_every_robot_move() -> None:
    session = GameSession(difficulty=HARD, seed=42)
    human_moves = iter((5, 3, 4, 8))
    while session.is_active:
        if session.turn == ROBOT:
            move = session.request_robot_move()
            assert session.board.cell(move) is None
            session.confirm_robot_move()
        else:
            session.play_human_move(next(human_moves))
    assert session.result == DRAW
