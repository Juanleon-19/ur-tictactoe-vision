from __future__ import annotations

from main import build_parser, run_modbus_check
from ur_tictactoe.communication import STATUS_READY


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.writes: list[int] = []
        self.closed = False
        self.__class__.instances.append(self)

    def connect(self) -> None:
        pass

    def read_status(self) -> int:
        return STATUS_READY

    def write_command(self, command: int) -> None:
        self.writes.append(command)

    def close(self) -> None:
        self.closed = True

    def clear_command(self) -> None:
        self.writes.append(0)


def test_modbus_check_is_read_only_by_default(capsys) -> None:
    FakeClient.instances.clear()
    args = build_parser().parse_args(["modbus-check", "--host", "test-host"])
    assert run_modbus_check(args, FakeClient) == 0
    client = FakeClient.instances[-1]
    assert client.writes == []
    assert client.closed
    assert "STATUS = READY" in capsys.readouterr().out


def test_modbus_check_requires_allow_write(capsys) -> None:
    FakeClient.instances.clear()
    args = build_parser().parse_args(
        ["modbus-check", "--host", "test-host", "--command", "5"]
    )
    assert run_modbus_check(args, FakeClient) == 2
    assert FakeClient.instances == []
    assert "requires --allow-write" in capsys.readouterr().err


def test_modbus_check_explicit_write_reports_register(capsys) -> None:
    FakeClient.instances.clear()
    args = build_parser().parse_args(
        [
            "modbus-check",
            "--host",
            "test-host",
            "--command",
            "5",
            "--allow-write",
        ]
    )
    assert run_modbus_check(args, FakeClient) == 0
    assert FakeClient.instances[-1].writes == [5]
    assert "COMMAND_REGISTER=128" in capsys.readouterr().out


def test_modbus_handshake_observes_busy_done_hold_and_ready(capsys) -> None:
    class HandshakeClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(host, port)
            self.statuses = iter((STATUS_READY, 1, 2, 2, STATUS_READY))

        def read_status(self) -> int:
            return next(self.statuses)

    args = build_parser().parse_args(
        ["modbus-check", "--host", "test-host", "--handshake", "5"]
    )
    assert run_modbus_check(args, HandshakeClient) == 0
    assert HandshakeClient.instances[-1].writes == [5, 0]
    output = capsys.readouterr().out
    assert "STATUS = BUSY" in output
    assert "STATUS HELD = DONE" in output


def test_main_dispatches_read_only_modbus(monkeypatch, capsys) -> None:
    import main as cli

    FakeClient.instances.clear()
    monkeypatch.setattr(cli, "ModbusClient", FakeClient)
    monkeypatch.setattr(cli.sys, "argv", ["main.py", "modbus-check", "--host", "test-host"])
    assert cli.main() == 0
    client = FakeClient.instances[-1]
    assert client.writes == []
    assert client.closed
    assert "STATUS = READY" in capsys.readouterr().out


def test_main_dispatches_handshake_and_resets_command(monkeypatch, capsys) -> None:
    import main as cli

    class HandshakeClient(FakeClient):
        def __init__(self, host, port):
            super().__init__(host, port)
            self.statuses = iter((0, 1, 2, 2, 0))

        def read_status(self):
            return next(self.statuses)

    monkeypatch.setattr(cli, "ModbusClient", HandshakeClient)
    monkeypatch.setattr(cli.sys, "argv", [
        "main.py", "modbus-check", "--host", "test-host", "--handshake", "5"
    ])
    assert cli.main() == 0
    client = HandshakeClient.instances[-1]
    assert client.writes == [5, 0]
    assert client.closed
    assert "STATUS HELD = DONE" in capsys.readouterr().out


def test_main_dispatches_explicit_command(monkeypatch) -> None:
    import main as cli

    monkeypatch.setattr(cli, "ModbusClient", FakeClient)
    monkeypatch.setattr(cli.sys, "argv", [
        "main.py", "modbus-check", "--host", "test-host",
        "--command", "5", "--allow-write"
    ])
    assert cli.main() == 0
    assert FakeClient.instances[-1].writes == [5]
    assert FakeClient.instances[-1].closed
