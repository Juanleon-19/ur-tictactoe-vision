from __future__ import annotations

import pytest

from main import build_parser, run_game
from ur_tictactoe.game import (
    EXPERTO,
    INTERMEDIO,
    NORMAL_ACTION,
    PICARO,
    PICARO_ACTION,
    ROBOT,
    ROBOT_WINS,
    Board,
    GameSession,
    O,
    RobotDecision,
    X,
    choose_move,
    choose_robot_decision,
)


def test_experto_preserves_full_depth_behavior() -> None:
    board = Board((X, O, None, None, X, O, None, None, None))
    assert choose_move(board, X, O, EXPERTO) == 9


def test_intermedio_preserves_immediate_win_and_block() -> None:
    win = Board((O, O, None, X, X, None, None, None, None))
    block = Board((X, X, None, None, O, None, None, None, None))
    assert choose_move(win, O, X, INTERMEDIO) == 3
    assert choose_move(block, O, X, INTERMEDIO) == 3


def test_picaro_is_a_valid_session_mode() -> None:
    assert GameSession(difficulty=PICARO).difficulty == PICARO


def test_picaro_plays_normal_when_robot_can_force_a_win() -> None:
    board = Board((X, X, None, O, O, None, None, None, None))
    decision = choose_robot_decision(board, O, X, PICARO)
    assert decision == RobotDecision(NORMAL_ACTION, 6)
    assert decision.cell in board.available_moves()


def test_picaro_replaces_when_best_normal_result_is_draw() -> None:
    board = Board((None, None, None, None, None, None, None, None, X))
    assert choose_robot_decision(board, O, X, PICARO) == RobotDecision(
        PICARO_ACTION, 9
    )


def test_picaro_replaces_when_normal_play_would_lose() -> None:
    board = Board((None, None, None, None, None, X, None, O, X))
    assert choose_robot_decision(board, O, X, PICARO) == RobotDecision(
        PICARO_ACTION, 9
    )


def test_picaro_uses_normal_move_without_a_human_piece() -> None:
    decision = choose_robot_decision(Board(), X, O, PICARO, seed=42)
    assert decision is not None
    assert decision.action == NORMAL_ACTION
    assert decision.cell in range(1, 10)


def test_picaro_only_targets_human_cells_and_selects_best_replacement() -> None:
    board = Board((None, None, None, None, None, X, None, O, X))
    decision = choose_robot_decision(board, O, X, PICARO)
    assert decision == RobotDecision(PICARO_ACTION, 9)
    assert board.cell(decision.cell) == X
    assert decision.cell != 8
    assert decision.cell not in board.available_moves()


def test_normal_board_still_rejects_overwrite() -> None:
    board = Board((X, None, None, None, None, None, None, None, None))
    with pytest.raises(ValueError, match="already occupied"):
        board.make_move(1, O)


def _picaro_session(cells: tuple[str | None, ...]) -> GameSession:
    session = GameSession(difficulty=PICARO, human_first=True)
    session.board = Board(cells)
    session.turn = ROBOT
    return session


def test_pending_picaro_action_does_not_modify_board() -> None:
    session = _picaro_session((None, None, None, None, None, X, None, O, X))
    original = session.board.cells
    session.request_robot_move()
    assert session.pending_robot_decision == RobotDecision(PICARO_ACTION, 9)
    assert session.board.cells == original


def test_confirming_picaro_replaces_piece_and_passes_turn() -> None:
    session = _picaro_session((None, None, None, None, None, X, None, O, X))
    occupied_before = sum(cell is not None for cell in session.board.cells)
    session.request_robot_move()
    session.confirm_robot_move()
    assert session.board.cell(9) == O
    assert sum(cell is not None for cell in session.board.cells) == occupied_before
    assert session.pending_robot_decision is None
    assert session.turn == "human"


def test_cancelling_picaro_does_not_modify_board() -> None:
    session = _picaro_session((None, None, None, None, None, X, None, O, X))
    original = session.board.cells
    session.request_robot_move()
    session.cancel_robot_move()
    assert session.board.cells == original
    assert session.pending_robot_move is None
    assert session.pending_robot_decision is None


def test_picaro_victory_ends_session() -> None:
    session = _picaro_session((None, None, None, None, X, X, X, O, O))
    assert session.request_robot_move() == 7
    session.confirm_robot_move()
    assert session.result == ROBOT_WINS
    assert session.turn is None


@pytest.mark.parametrize("difficulty", [EXPERTO, INTERMEDIO, PICARO])
def test_cli_accepts_spanish_difficulty_names(difficulty: str) -> None:
    args = build_parser().parse_args(["game", "--difficulty", difficulty])
    assert args.difficulty == difficulty


@pytest.mark.parametrize("difficulty", ["hard", "intermediate"])
def test_cli_keeps_small_legacy_compatibility(difficulty: str) -> None:
    args = build_parser().parse_args(["game", "--difficulty", difficulty])
    assert args.difficulty == difficulty


def test_cli_reports_picaro_replacement_in_spanish(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    moves = iter(("9", "8", "7"))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(moves))
    assert run_game(human_first=True, difficulty=PICARO) == 0
    output = capsys.readouterr().out
    assert "Robot usa modo PÍCARO" in output
    assert "reemplaza la ficha humana de la celda 9" in output
