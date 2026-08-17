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
    ModbusConnectionError,
    ModbusResponseError,
)
from ur_tictactoe.communication.protocol import validate_command
from ur_tictactoe.game import ROBOT, GameSession


class FakeResponse:
    def __init__(self, registers: list[int] | None = None, error: bool = False) -> None:
        self.registers = registers
        self._error = error

    def isError(self) -> bool:
        return self._error


class FakeTransport:
    def __init__(
        self,
        statuses: tuple[int, ...] = (),
        connect_result: bool = True,
        error_response: bool = False,
    ) -> None:
        self.statuses = list(statuses)
        self.connect_result = connect_result
        self.error_response = error_response
        self.writes: list[tuple[int, int]] = []
        self.reads: list[tuple[int, int]] = []
        self.closed = False

    def connect(self) -> bool:
        return self.connect_result

    def close(self) -> None:
        self.closed = True

    def write_register(self, address: int, value: int) -> FakeResponse:
        self.writes.append((address, value))
        return FakeResponse(error=self.error_response)

    def read_holding_registers(self, address: int, *, count: int) -> FakeResponse:
        self.reads.append((address, count))
        return FakeResponse(
            registers=[self.statuses.pop(0)] if self.statuses else None,
            error=self.error_response,
        )


@pytest.mark.parametrize("command", range(1, 10))
def test_cells_one_through_nine_are_valid_commands(command: int) -> None:
    assert validate_command(command) == command


def test_idle_command_zero_is_valid() -> None:
    assert validate_command(0) == 0


@pytest.mark.parametrize("command", [-1, 10, True])
def test_command_outside_range_is_rejected(command: int) -> None:
    with pytest.raises(ValueError, match="0 to 9"):
        validate_command(command)


@pytest.mark.parametrize(
    "status",
    [STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_ERROR],
)
def test_protocol_status_is_recognized(status: int) -> None:
    client = ModbusClient("test-host", transport=FakeTransport((status,)))
    assert client.read_status() == status


def test_write_command_uses_project_command_register() -> None:
    transport = FakeTransport()
    ModbusClient("test-host", transport=transport).write_command(5)
    assert transport.writes == [(COMMAND_REGISTER, 5)]


def test_clear_command_writes_idle_zero() -> None:
    transport = FakeTransport()
    ModbusClient("test-host", transport=transport).clear_command()
    assert transport.writes == [(COMMAND_REGISTER, 0)]


def test_read_status_uses_project_status_register() -> None:
    transport = FakeTransport((STATUS_READY,))
    ModbusClient("test-host", transport=transport).read_status()
    assert transport.reads == [(STATUS_REGISTER, 1)]


def test_connection_failure_has_clear_error() -> None:
    client = ModbusClient(
        "unreachable-test-host",
        transport=FakeTransport(connect_result=False),
    )
    with pytest.raises(ModbusConnectionError, match="Could not connect"):
        client.connect()


def test_modbus_error_response_has_clear_error() -> None:
    client = ModbusClient(
        "test-host",
        transport=FakeTransport(error_response=True),
    )
    with pytest.raises(ModbusResponseError, match="write COMMAND"):
        client.write_command(5)


def test_ready_busy_done_handshake_confirms_pending_robot_move() -> None:
    session = GameSession(seed=42)
    transport = FakeTransport((STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_READY))
    client = ModbusClient("test-host", transport=transport)

    assert client.read_status() == STATUS_READY
    pending = session.request_robot_move()
    client.write_command(pending)
    assert client.read_status() == STATUS_BUSY
    assert session.board.cell(pending) is None
    assert client.read_status() == STATUS_DONE

    session.confirm_robot_move()
    client.clear_command()
    assert client.read_status() == STATUS_READY

    assert session.board.cell(pending) == session.robot
    assert session.pending_robot_move is None
    assert transport.writes == [(COMMAND_REGISTER, pending), (COMMAND_REGISTER, 0)]


def test_error_status_cancels_move_without_changing_board() -> None:
    session = GameSession(seed=42)
    transport = FakeTransport((STATUS_READY, STATUS_ERROR))
    client = ModbusClient("test-host", transport=transport)
    original_board = session.board.cells

    assert client.read_status() == STATUS_READY
    pending = session.request_robot_move()
    client.write_command(pending)
    assert client.read_status() == STATUS_ERROR
    session.cancel_robot_move()

    assert session.board.cells == original_board
    assert session.pending_robot_move is None
    assert session.turn == ROBOT
    assert session.request_robot_move() in session.board.available_moves()
