"""Exercise the real CLI dispatch with an in-memory Modbus boundary only."""

import pytest

import main as cli
from ur_tictactoe.communication import COMMAND_REGISTER, STATUS_REGISTER


class FakeRobot:
    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.writes = []
        self.closed = False
        self.statuses = iter((0, 1, 2, 2, 0))
        self.instances.append(self)

    def connect(self):
        pass

    def read_status(self):
        return next(self.statuses)

    def write_command(self, cell):
        self.writes.append(cell)

    def clear_command(self):
        self.write_command(0)

    def close(self):
        self.closed = True


@pytest.fixture
def robot_cli(monkeypatch):
    FakeRobot.instances.clear()
    monkeypatch.setattr(cli, "ModbusClient", FakeRobot)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)

    def run(*flags):
        monkeypatch.setattr(cli.sys, "argv", [
            "main.py", "robot-test", "--host", "test-host", *flags,
        ])
        return cli.main()

    return run


def test_robot_test_refuses_without_permission_before_connecting(robot_cli, capsys):
    assert robot_cli("--cell", "5") == 2
    assert FakeRobot.instances == []
    assert "requires --allow-motion" in capsys.readouterr().err


@pytest.mark.parametrize("cell", ["0", "10", "-1", "x"])
def test_robot_test_rejects_invalid_cell(robot_cli, cell):
    with pytest.raises(SystemExit) as exc:
        robot_cli("--cell", cell, "--allow-motion")
    assert exc.value.code == 2
    assert FakeRobot.instances == []


def test_robot_test_uses_existing_handshake_and_only_sends_cell(robot_cli, capsys):
    assert (COMMAND_REGISTER, STATUS_REGISTER) == (128, 129)
    assert robot_cli("--cell", "5", "--allow-motion") == 0
    robot = FakeRobot.instances[-1]
    assert robot.writes == [5, 0]
    assert robot.closed
    output = capsys.readouterr().out
    assert "STATUS = BUSY" in output
    assert "STATUS HELD = DONE" in output


def test_robot_test_reuses_common_wait_with_configurable_timeout(robot_cli, monkeypatch):
    calls = []
    original_wait = cli._wait_for_status

    def record(client, expected, timeout):
        calls.append((expected, timeout))
        return original_wait(client, expected, timeout)

    monkeypatch.setattr(cli, "_wait_for_status", record)
    assert robot_cli("--cell", "1", "--allow-motion", "--timeout", "12") == 0
    assert calls == [(1, 12), (2, 12), (0, 12)]


def test_robot_test_does_not_send_when_status_is_not_ready(robot_cli, monkeypatch):
    monkeypatch.setattr(FakeRobot, "read_status", lambda self: 1)
    assert robot_cli("--cell", "5", "--allow-motion") == 1
    assert FakeRobot.instances[-1].writes == []
    assert FakeRobot.instances[-1].closed


def test_robot_test_error_resets_without_retry(robot_cli, monkeypatch):
    statuses = iter((0, 1, 3))
    monkeypatch.setattr(FakeRobot, "read_status", lambda self: next(statuses))
    assert robot_cli("--cell", "5", "--allow-motion") == 1
    assert FakeRobot.instances[-1].writes == [5, 0]
    assert FakeRobot.instances[-1].closed


def test_robot_test_timeout_resets_without_retry(robot_cli, monkeypatch):
    clock = iter((0, 2))
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    assert robot_cli("--cell", "5", "--allow-motion", "--timeout", "1") == 1
    assert FakeRobot.instances[-1].writes == [5, 0]
    assert FakeRobot.instances[-1].closed


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_robot_test_rejects_invalid_timeout(robot_cli, timeout):
    with pytest.raises(SystemExit) as exc:
        robot_cli("--cell", "5", "--allow-motion", "--timeout", timeout)
    assert exc.value.code == 2
    assert FakeRobot.instances == []
