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
