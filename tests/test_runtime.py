from __future__ import annotations

import pytest

from ur_tictactoe.communication import (
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    ModbusConnectionError,
)
from ur_tictactoe.game import GameSession
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState
from ur_tictactoe.vision.board_observer import CellState, PhysicalBoardState


def physical(*occupied: int, ready: bool = True, uncertain: tuple[int, ...] = ()) -> PhysicalBoardState:
    cells = {
        cell: (
            CellState.UNCERTAIN
            if cell in uncertain
            else CellState.OCCUPIED
            if cell in occupied
            else CellState.FREE
        )
        for cell in range(1, 10)
    }
    return PhysicalBoardState(cells, {}, ready, 3, {})


class FakeModbus:
    def __init__(self, statuses: tuple[int, ...] = ()) -> None:
        self.statuses = list(statuses)
        self.writes: list[int] = []
        self.clear_count = 0
        self.error: Exception | None = None

    def read_status(self) -> int:
        if self.error:
            raise self.error
        return self.statuses.pop(0)

    def write_command(self, cell: int) -> None:
        self.writes.append(cell)

    def clear_command(self) -> None:
        self.clear_count += 1


def runtime(human_first: bool = True, statuses: tuple[int, ...] = ()) -> tuple[PhysicalGameRuntime, FakeModbus]:
    modbus = FakeModbus(statuses)
    result = PhysicalGameRuntime(GameSession(human_first=human_first, seed=42), modbus)
    return result, modbus


def test_empty_board_starts_game() -> None:
    game, _ = runtime()
    assert game.start(physical())
    assert game.state == RuntimeState.WAITING_HUMAN


def test_occupied_board_is_rejected() -> None:
    game, _ = runtime()
    assert not game.start(physical(4))
    assert game.snapshot().last_error == "BOARD_NOT_EMPTY"


def test_one_new_occupation_plays_human_move() -> None:
    game, _ = runtime()
    game.start(physical())
    assert game.update_board(physical(4)) == 4
    assert game.session.board.cell(4) == game.session.human


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (physical(2, 3), "INCONSISTENT_BOARD_CHANGE"),
        (physical(uncertain=(2,)), "BOARD_UNCERTAIN"),
    ],
)
def test_invalid_human_observation_does_not_play(state: PhysicalBoardState, reason: str) -> None:
    game, _ = runtime()
    game.start(physical())
    game.update_board(state)
    assert game.session.board.cells == (None,) * 9
    assert reason in (game.last_error or "")


def test_removed_logical_cell_is_not_accepted() -> None:
    game, _ = runtime()
    game.start(physical())
    game.session.board.make_move(1, game.session.robot)
    game.update_board(physical(2))
    assert game.session.board.cell(2) is None
    assert "removed=[1]" in (game.last_error or "")


def test_robot_requests_only_one_move_and_ready_sends_once() -> None:
    game, modbus = runtime(False, (STATUS_READY, STATUS_READY))
    game.start(physical())
    game.poll_robot()
    pending = game.session.pending_robot_move
    game.poll_robot()
    assert pending is not None
    assert game.session.pending_robot_move == pending
    assert modbus.writes == [pending]


def test_busy_does_not_modify_board_or_use_observation() -> None:
    game, _ = runtime(False, (STATUS_BUSY,))
    game.start(physical())
    game.poll_robot()
    game.update_board(physical(1, 2, 3))
    assert game.state == RuntimeState.ROBOT_BUSY
    assert game.session.board.cells == (None,) * 9


def test_done_waits_for_visual_verification() -> None:
    game, _ = runtime(False, (STATUS_DONE,))
    game.start(physical())
    game.poll_robot()
    assert game.state == RuntimeState.VERIFYING_ROBOT
    assert game.session.board.cells == (None,) * 9
    assert game.session.pending_robot_move is not None


def test_correct_verification_confirms_and_clears_command() -> None:
    game, modbus = runtime(False, (STATUS_READY, STATUS_DONE))
    game.start(physical())
    game.poll_robot()
    expected = game.session.pending_robot_move
    game.poll_robot()
    game.update_board(physical(expected))
    assert game.session.board.cell(expected) == game.session.robot
    assert game.session.pending_robot_move is None
    assert modbus.clear_count == 1
    assert not game.command_sent


@pytest.mark.parametrize("unexpected", [(), (8,)])
def test_invalid_robot_verification_does_not_confirm(unexpected: tuple[int, ...]) -> None:
    game, modbus = runtime(False, (STATUS_DONE,))
    game.start(physical())
    game.poll_robot()
    expected = game.session.pending_robot_move
    observed = unexpected if expected not in unexpected else (9,)
    game.update_board(physical(*observed))
    assert game.session.pending_robot_move == expected
    assert game.session.board.cells == (None,) * 9
    assert modbus.clear_count == 0


def test_error_status_cancels_simulated_move_without_reset_command() -> None:
    game, modbus = runtime(False, (STATUS_READY, STATUS_ERROR))
    game.start(physical())
    game.poll_robot()
    game.poll_robot()
    assert game.state == RuntimeState.ERROR
    assert game.session.pending_robot_move is None
    assert modbus.clear_count == 0


def test_modbus_exception_enters_error_with_cause() -> None:
    game, modbus = runtime(False)
    game.start(physical())
    modbus.error = ModbusConnectionError("offline")
    game.poll_robot()
    assert game.state == RuntimeState.ERROR
    assert game.error_cause is modbus.error


def test_complete_simulated_game_reaches_game_over() -> None:
    game, modbus = runtime(True)
    game.start(physical())
    occupied: set[int] = set()

    while game.session.is_active:
        if game.session.turn == "human":
            move = game.session.board.available_moves()[0]
            occupied.add(move)
            game.update_board(physical(*occupied))
        else:
            modbus.statuses.extend((STATUS_READY, STATUS_DONE))
            game.poll_robot()
            expected = game.session.pending_robot_move
            game.poll_robot()
            occupied.add(expected)
            game.update_board(physical(*occupied))

    assert game.state == RuntimeState.GAME_OVER
    assert game.snapshot().result != "active"
