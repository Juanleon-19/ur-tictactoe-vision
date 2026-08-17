from __future__ import annotations

import pytest

from ur_tictactoe.communication import (
    COMMAND_REGISTER,
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    STATUS_REGISTER,
    ModbusClient,
)
from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.controller import GameController
from ur_tictactoe.game import DRAW, HARD, HUMAN, INTERMEDIATE, ROBOT, GameSession
from ur_tictactoe.vision.move_detector import HumanMoveDetector, cell_to_marker_id

ALL_VISIBLE = set(CELL_IDS)


class FakeResponse:
    def __init__(self, registers: list[int] | None = None) -> None:
        self.registers = registers

    def isError(self) -> bool:
        return False


class FakeTransport:
    def __init__(self, statuses: tuple[int, ...] = ()) -> None:
        self.statuses = list(statuses)
        self.writes: list[tuple[int, int]] = []
        self.reads: list[tuple[int, int]] = []

    def read_holding_registers(self, address: int, *, count: int) -> FakeResponse:
        self.reads.append((address, count))
        return FakeResponse([self.statuses.pop(0)])

    def write_register(self, address: int, value: int) -> FakeResponse:
        self.writes.append((address, value))
        return FakeResponse()


def make_controller(
    *,
    statuses: tuple[int, ...] = (),
    human_first: bool = False,
    difficulty: str = HARD,
    stable_frames: int = 2,
) -> tuple[GameController, FakeTransport]:
    transport = FakeTransport(statuses)
    controller = GameController(
        HumanMoveDetector(stable_frames=stable_frames),
        GameSession(difficulty=difficulty, human_first=human_first, seed=42),
        ModbusClient("test-host", transport=transport),
    )
    return controller, transport


def test_human_turn_without_disappearance_does_nothing() -> None:
    controller, transport = make_controller(human_first=True)
    assert controller.step(True, ALL_VISIBLE) is None
    assert controller.session.board.cells == (None,) * 9
    assert transport.reads == []


def test_stable_disappearance_returns_and_applies_human_move() -> None:
    controller, _ = make_controller(human_first=True)
    visible = ALL_VISIBLE - {14}
    assert controller.step(True, visible) is None
    assert controller.step(True, visible) == 5
    assert controller.session.board.cell(5) == controller.session.human
    assert controller.session.turn == ROBOT


def test_visual_event_is_ignored_during_robot_turn() -> None:
    controller, _ = make_controller(statuses=(STATUS_BUSY,), stable_frames=1)
    controller.step(True, ALL_VISIBLE - {14})
    assert controller.session.board.cell(5) is None
    assert controller.session.pending_robot_move is not None


def test_robot_turn_requests_pending_move() -> None:
    controller, _ = make_controller(statuses=(STATUS_BUSY,))
    controller.step(True, ALL_VISIBLE)
    assert controller.session.pending_robot_move in range(1, 10)


def test_ready_writes_command_exactly_once() -> None:
    controller, transport = make_controller(
        statuses=(STATUS_READY, STATUS_READY),
    )
    controller.step(True, ALL_VISIBLE)
    pending = controller.session.pending_robot_move
    controller.step(True, ALL_VISIBLE)
    assert transport.writes == [(COMMAND_REGISTER, pending)]
    assert controller.command_sent


def test_busy_keeps_pending_move_and_board_unchanged() -> None:
    controller, _ = make_controller(statuses=(STATUS_READY, STATUS_BUSY))
    controller.step(True, ALL_VISIBLE)
    pending = controller.session.pending_robot_move
    controller.step(True, ALL_VISIBLE)
    assert controller.session.pending_robot_move == pending
    assert controller.session.board.cell(pending) is None


def test_done_confirms_board_clears_command_and_returns_human_turn() -> None:
    controller, transport = make_controller(
        statuses=(STATUS_READY, STATUS_BUSY, STATUS_DONE),
    )
    controller.step(True, ALL_VISIBLE)
    pending = controller.session.pending_robot_move
    controller.step(True, ALL_VISIBLE)
    controller.step(True, ALL_VISIBLE)
    assert controller.session.board.cell(pending) == controller.session.robot
    assert controller.session.pending_robot_move is None
    assert controller.session.turn == HUMAN
    assert transport.writes[-1] == (COMMAND_REGISTER, 0)
    assert not controller.command_sent


def test_error_cancels_without_board_change_and_allows_retry() -> None:
    controller, transport = make_controller(
        statuses=(STATUS_READY, STATUS_ERROR, STATUS_READY),
    )
    original = controller.session.board.cells
    controller.step(True, ALL_VISIBLE)
    controller.step(True, ALL_VISIBLE)
    assert controller.session.board.cells == original
    assert controller.session.pending_robot_move is None
    assert controller.session.turn == ROBOT
    assert transport.writes[-1] == (COMMAND_REGISTER, 0)

    controller.step(True, ALL_VISIBLE)
    assert controller.session.pending_robot_move is not None
    assert controller.command_sent


def test_game_over_does_not_read_status_or_write_command() -> None:
    controller, transport = make_controller(
        human_first=True,
        difficulty=INTERMEDIATE,
        stable_frames=1,
    )
    session = controller.session
    for human_move in (3, 7, 9):
        session.play_human_move(human_move)
        session.request_robot_move()
        session.confirm_robot_move()
    session.play_human_move(8)
    assert not session.is_active

    controller.step(True, ALL_VISIBLE)
    assert transport.reads == []
    assert transport.writes == []


@pytest.mark.parametrize("difficulty", [HARD, INTERMEDIATE])
def test_controller_uses_session_difficulty(difficulty: str) -> None:
    controller, transport = make_controller(
        difficulty=difficulty,
        statuses=(STATUS_READY,),
    )
    controller.step(True, ALL_VISIBLE)
    assert controller.session.pending_robot_move is not None
    assert transport.writes[0][0] == COMMAND_REGISTER


def test_complete_simulated_game_reaches_draw() -> None:
    statuses = (STATUS_READY, STATUS_BUSY, STATUS_DONE) * 5
    controller, transport = make_controller(statuses=statuses, stable_frames=1)
    human_moves = (5, 3, 4, 8)

    for human_move in human_moves:
        controller.step(True, ALL_VISIBLE)
        controller.step(True, ALL_VISIBLE)
        controller.step(True, ALL_VISIBLE)
        assert controller.session.turn == HUMAN

        missing = {
            cell_to_marker_id(cell)
            for cell in range(1, 10)
            if controller.session.board.cell(cell) is not None
        }
        missing.add(cell_to_marker_id(human_move))
        assert controller.step(True, ALL_VISIBLE - missing) == human_move

    controller.step(True, ALL_VISIBLE)
    controller.step(True, ALL_VISIBLE)
    controller.step(True, ALL_VISIBLE)

    assert controller.session.result == DRAW
    assert not controller.session.is_active
    assert len(transport.writes) == 10
    assert transport.reads == [(STATUS_REGISTER, 1)] * 15


def test_end_to_end_error_leaves_robot_ready_to_retry() -> None:
    controller, transport = make_controller(
        statuses=(STATUS_READY, STATUS_ERROR, STATUS_READY),
        human_first=True,
        stable_frames=1,
    )
    assert controller.step(True, ALL_VISIBLE - {14}) == 5
    human_board = controller.session.board.cells

    controller.step(True, ALL_VISIBLE)
    failed_move = controller.session.pending_robot_move
    controller.step(True, ALL_VISIBLE)

    assert controller.session.board.cells == human_board
    assert controller.session.board.cell(failed_move) is None
    assert controller.session.pending_robot_move is None
    assert controller.session.turn == ROBOT

    controller.step(True, ALL_VISIBLE)
    assert controller.session.pending_robot_move is not None
    assert transport.writes[-1][0] == COMMAND_REGISTER
