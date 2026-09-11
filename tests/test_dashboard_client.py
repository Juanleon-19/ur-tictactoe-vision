"""CB3 Dashboard wire protocol exercised entirely with in-memory sockets."""

import pytest

from ur_tictactoe.communication.dashboard_client import DashboardClient


class Socket:
    def __init__(self, responses):
        self.responses = bytearray(responses)
        self.sent = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.closed = True

    def recv(self, count):
        data = bytes(self.responses[:count])
        del self.responses[:count]
        return data

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, timeout):
        assert 0 < timeout <= 2


def install(monkeypatch, program, mode=b"Robotmode: RUNNING\n"):
    connection = Socket(b"Connected: Universal Robots Dashboard Server\n" + program + mode)

    def connect(address, *, timeout):
        assert address == ("fake-host", 29999)
        assert timeout == 2
        return connection

    monkeypatch.setattr("ur_tictactoe.communication.dashboard_client.socket.create_connection", connect)
    return connection


@pytest.mark.parametrize("response,state", [
    (b"PLAYING controller.urp\n", "EJECUTANDO"), (b"STOPPED\n", "DETENIDO"),
    (b"PAUSED controller.urp\n", "PAUSADO"),
    (b"Command is not supported\n", "DESCONOCIDO"), (b"\n", "DESCONOCIDO"),
])
def test_cb3_states_and_only_allowed_queries(monkeypatch, response, state):
    connection = install(monkeypatch, response)
    snapshot = DashboardClient("fake-host").snapshot()
    assert snapshot.availability == "DISPONIBLE"
    assert snapshot.program_state == state
    assert snapshot.robot_mode == "RUNNING"
    assert connection.sent == [b"programState\n", b"robotmode\n"]
    assert connection.closed


def test_unsupported_mode_is_independent_of_program_state(monkeypatch):
    connection = install(monkeypatch, b"PLAYING test.urp\n", b"Unknown command\n")
    snapshot = DashboardClient("fake-host").snapshot()
    assert snapshot.program_state == "EJECUTANDO"
    assert snapshot.robot_mode == "DESCONOCIDO"
    assert connection.closed


@pytest.mark.parametrize("response", [b"PAUSED", b"\xff\n", b"x" * 4096])
def test_incomplete_invalid_or_oversized_response_closes_session(monkeypatch, response):
    connection = install(monkeypatch, response, b"")
    snapshot = DashboardClient("fake-host").snapshot()
    assert snapshot.availability == "NO DISPONIBLE"
    assert snapshot.program_state == "DESCONOCIDO"
    assert connection.closed
    assert connection.sent == [b"programState\n"]


def test_total_deadline_no_retry(monkeypatch):
    connection = install(monkeypatch, b"PLAYING\n")
    clock = [0.0]
    monkeypatch.setattr("ur_tictactoe.communication.dashboard_client.monotonic", lambda: clock[0])
    original_recv = connection.recv

    def slow_byte(count):
        clock[0] += 0.3
        return original_recv(count)

    connection.recv = slow_byte
    assert DashboardClient("fake-host").snapshot().availability == "NO DISPONIBLE"
    assert clock[0] < 2.5
    assert connection.closed and connection.sent == []
