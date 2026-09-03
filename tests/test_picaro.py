from __future__ import annotations

import pytest

from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.game import (
    HUMAN,
    NORMAL_ACTION,
    PICARO,
    PICARO_ACTION,
    ROBOT,
    Board,
    GameSession,
    O,
    X,
)
from ur_tictactoe.runtime import RuntimeState


def session_with_board(cells: tuple[str | None, ...], turn: str) -> GameSession:
    session = GameSession(difficulty=PICARO, human_first=True, seed=42)
    session.board = Board(cells)
    session.turn = turn
    return session


def test_both_players_start_with_picaro_available() -> None:
    session = GameSession(difficulty=PICARO)
    assert session.robot_picaro_available
    assert session.human_picaro_available


def test_human_picaro_replaces_robot_piece_and_passes_turn() -> None:
    session = session_with_board((O, None, None, None, X, None, None, None, None), HUMAN)
    session.play_human_picaro(1)
    assert session.board.cell(1) == X
    assert session.turn == ROBOT
    assert not session.human_picaro_available


@pytest.mark.parametrize("cell", [2, 5])
def test_human_picaro_rejects_own_and_empty_cells(cell: int) -> None:
    session = session_with_board((O, None, None, None, X, None, None, None, None), HUMAN)
    with pytest.raises(ValueError, match="robot cell"):
        session.play_human_picaro(cell)
    assert session.human_picaro_available


def test_human_can_use_picaro_only_once() -> None:
    session = session_with_board((O, O, None, None, X, None, None, None, None), HUMAN)
    session.play_human_picaro(1)
    session.turn = HUMAN
    with pytest.raises(ValueError, match="already been used"):
        session.play_human_picaro(2)


def test_robot_can_use_picaro_only_once() -> None:
    session = session_with_board((None, None, None, None, None, None, None, O, X), ROBOT)
    assert session.request_robot_move() == 9
    assert session.pending_robot_decision.action == PICARO_ACTION
    session.confirm_robot_move()
    assert not session.robot_picaro_available


def test_robot_with_consumed_picaro_uses_normal_move() -> None:
    session = session_with_board((None, None, None, None, None, None, None, O, X), ROBOT)
    session.robot_picaro_available = False
    session.request_robot_move()
    assert session.pending_robot_decision.action == NORMAL_ACTION
    assert session.board.cell(session.pending_robot_move) is None


def test_new_game_restores_both_picaro_resources() -> None:
    app = GameApplication(simulation=True)
    assert app.new_game(PICARO, human_first=True)
    app.session.human_picaro_available = False
    app.session.robot_picaro_available = False
    assert app.new_game(PICARO, human_first=False)
    assert app.snapshot().human_picaro_available
    assert app.snapshot().robot_picaro_available


def test_human_picaro_can_finish_the_game() -> None:
    session = session_with_board((X, X, O, None, O, None, None, None, None), HUMAN)
    session.play_human_picaro(3)
    assert session.result == "human_wins"
    assert session.turn is None


def test_simulation_snapshot_exposes_human_picaro() -> None:
    app = GameApplication(simulation=True)
    assert app.new_game(PICARO, human_first=True)
    snapshot = app.snapshot()
    assert snapshot.simulation and snapshot.human_picaro_available


def test_real_mode_keeps_picaro_disabled() -> None:
    app = GameApplication(simulation=False)
    assert not app.new_game(PICARO, human_first=True)
    assert not app.play_human_picaro(1)
    assert app.snapshot().last_error == "PICARO_SIMULATION_ONLY"


def test_complete_simulation_uses_picaro_on_both_sides() -> None:
    app = GameApplication(simulation=True)
    assert app.new_game(PICARO, human_first=True)
    for _ in range(100):
        snapshot = app.snapshot()
        if snapshot.runtime_state == RuntimeState.GAME_OVER:
            break
        if snapshot.runtime_state == RuntimeState.WAITING_HUMAN:
            robot_cells = [i + 1 for i, value in enumerate(snapshot.board) if value == snapshot.robot_symbol]
            if snapshot.human_picaro_available and robot_cells:
                assert app.play_human_picaro(robot_cells[0])
            else:
                normal = next(i + 1 for i, value in enumerate(snapshot.board) if value is None)
                assert app.play_human_cell(normal)
        else:
            app.update()
    snapshot = app.snapshot()
    assert snapshot.runtime_state == RuntimeState.GAME_OVER
    assert not snapshot.human_picaro_available
    assert not snapshot.robot_picaro_available
    assert snapshot.result == "robot_wins"
