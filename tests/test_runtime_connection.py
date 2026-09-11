"""Real runtime with an in-memory transport; never opens a socket."""

import pytest
from pymodbus.exceptions import ConnectionException

from ur_tictactoe.communication import ModbusClient, ModbusConnectionError
from ur_tictactoe.game import GameSession
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState
from test_runtime import physical
from test_modbus_client import FakeTransport


class Transport(FakeTransport):
    def __init__(self, statuses=()):
        super().__init__(statuses)
        self.active = False
        self.connects = self.closes = 0
        self.failure = None

    def connect(self):
        assert not self.active
        self.connects += 1
        if self.failure == "connect":
            raise ConnectionException("offline")
        self.active = True
        return True

    def close(self):
        self.active = False
        self.closes += 1

    def read_holding_registers(self, *args, **kwargs):
        if not self.active or self.failure == "read":
            raise ConnectionException("idle socket lost")
        return super().read_holding_registers(*args, **kwargs)

    def write_register(self, *args):
        assert self.active
        response = super().write_register(*args)
        if self.failure == "write":
            raise ConnectionException("command delivered; reply lost")
        return response


def setup(statuses=()):
    transport = Transport(statuses)
    now = [0.0]
    runtime = PhysicalGameRuntime(GameSession(human_first=True, seed=42),
                                  ModbusClient("test.invalid", transport=transport),
                                  manage_connection=True, clock=lambda: now[0])
    assert runtime.start(physical())
    return runtime, transport, now


def test_fresh_connection_each_turn_and_closed_through_long_human_waits():
    game, client, now = setup([0, 1, 2, 0, 0, 1, 2, 0])
    occupied = set()
    for turn in range(2):
        assert not client.active
        now[0] += 3600  # No socket to expire while human deliberates.
        occupied.add(game.session.board.available_moves()[0])
        game.update_board(physical(*occupied))
        assert client.connects == turn
        game.poll_robot()
        target = game.session.pending_robot_move
        assert client.connects == turn + 1
        game.poll_robot()
        game.poll_robot()
        assert game.state == RuntimeState.VERIFYING_ROBOT
        game.update_board(physical(*occupied))
        assert client.writes[-1] == (128, target)  # Missing piece: no ACK.
        occupied.add(target)
        game.update_board(physical(*occupied))
        assert game.state == RuntimeState.ACKNOWLEDGING_ROBOT
        assert client.active
        game.poll_robot()
        assert game.state == RuntimeState.WAITING_HUMAN
        assert not client.active
    assert client.connects == client.closes == 2
    assert len([value for _, value in client.writes if value]) == 2
    assert all(address == 129 for address, _ in client.reads)


@pytest.mark.parametrize("failure", ["connect", "read", "write", "disconnect_after_command"])
def test_transport_failure_is_domain_error_no_resend_or_reset(failure):
    game, client, _ = setup([0, 1, 2])
    game.update_board(physical(1))
    if failure != "disconnect_after_command":
        client.failure = failure
    game.poll_robot()
    if failure == "disconnect_after_command":
        client.active = False
        game.poll_robot()
    assert game.state == RuntimeState.ERROR
    assert isinstance(game.error_cause, ModbusConnectionError)
    assert isinstance(game.error_cause.__cause__, ConnectionException)
    for _ in range(5):
        game.poll_robot()
        game.update_board(physical(1, 5))
    assert not client.active
    assert client.connects == client.closes == 1
    assert len(client.writes) == (1 if failure in ("write", "disconnect_after_command") else 0)
    assert all(value != 0 for _, value in client.writes)


@pytest.mark.parametrize("stage", ["moving", "verification", "ack"])
def test_timeout_stops_without_retry_or_reset(stage):
    game, client, now = setup([0, 1, 2])
    game.update_board(physical(1))
    game.poll_robot()
    now[0] = 20  # More than 15 s is allowed for a physical cycle.
    game.poll_robot()
    assert game.state == RuntimeState.ROBOT_BUSY
    if stage != "moving":
        game.poll_robot()
    if stage == "ack":
        game.update_board(physical(1, game.session.pending_robot_move))
    before = list(client.writes)
    now[0] += 61
    game.poll_robot()
    assert game.state == RuntimeState.ERROR
    assert isinstance(game.error_cause, TimeoutError)
    assert client.writes == before
    assert not client.active


@pytest.mark.parametrize("statuses", [(1,), (2,), (0, 2), (0, 1, 0)])
def test_unexpected_status_never_completes_or_acknowledges(statuses):
    game, client, _ = setup(statuses)
    game.update_board(physical(1))
    for _ in statuses:
        game.poll_robot()
    assert game.state == RuntimeState.ERROR
    assert all(value != 0 for _, value in client.writes)
    assert not client.active


def test_operator_stop_does_not_acknowledge_pending_motion():
    game, client, _ = setup([0])
    game.update_board(physical(1))
    game.poll_robot()
    game.stop()
    assert game.command_sent
    assert len(client.writes) == 1 and client.writes[0][1] != 0
    assert not client.active
