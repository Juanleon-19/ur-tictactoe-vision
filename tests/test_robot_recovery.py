"""Read-only recovery using injected camera, observer and Modbus transports."""

from threading import Event

import pytest

from ur_tictactoe.communication import ModbusClient, ModbusConnectionError
from ur_tictactoe.communication.dashboard_client import DashboardClient
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.game import HARD
from ur_tictactoe.runtime import RuntimeState
from test_real_backend import FakeModbus, RecordingObserver, make_backend, physical


def finish(app):
    app._robot_worker.join(3)
    assert not app.robot_busy
    assert not app._robot_worker.is_alive()


@pytest.mark.parametrize("action", ["refresh_status", "reconnect_robot"])
@pytest.mark.parametrize("status,controller,summary", [
    (0, "READY", "LISTO"), (1, "BUSY", "EN MOVIMIENTO"),
    (2, "DONE", "REQUIERE RECUPERACIÓN"), (3, "ERROR", "REQUIERE RECUPERACIÓN"), (99, "DESCONOCIDO", "REQUIERE RECUPERACIÓN"),
])
def test_fresh_read_only_recovery(action, status, controller, summary):
    old = FakeModbus(connect_error=ModbusConnectionError("offline"))
    backend = make_backend(modbus=old, observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    assert not app.open()
    app.update()
    camera, observer, observation = backend.camera, backend.observer, backend.last_observation
    counts = camera.open_calls, camera.read_calls, camera.close_calls
    assert app.snapshot().robot_status == "ERROR DE CONEXIÓN"
    fresh = FakeModbus((status,))
    backend._modbus_factory = lambda: fresh
    assert getattr(app, action)()
    finish(app)
    assert backend.modbus_client is fresh
    assert old.close_calls == 2  # Failed initial probe, then discard old connection.
    assert fresh.connect_calls == fresh.close_calls == 1
    assert old.commands == fresh.commands == []
    assert app.snapshot().robot_status == summary
    assert app.diagnostic_snapshot().modbus_status == "CONECTADO"
    assert app.diagnostic_snapshot().controller_status == controller
    assert backend.observer is observer and backend.last_observation is observation
    assert app._last_observation is observation
    assert app.snapshot().board_status == "LISTO"
    assert (camera.open_calls, camera.read_calls, camera.close_calls) == counts
    if status == 0:
        assert app.snapshot().last_error is None
        assert backend.last_error is None
    else:
        assert controller in app.snapshot().last_error
        fresh.statuses = [status]  # The start guard performs its own fresh read.
        assert not app.new_game(HARD, True)
    app.close()


@pytest.mark.parametrize("action", ["refresh_status", "reconnect_robot"])
def test_real_modbus_adapter_only_reads_status129(action):
    events = []

    class Transport:
        def connect(self):
            events.append("connect")
            return True

        def close(self):
            events.append("close")

        def read_holding_registers(self, address, *, count):
            events.append(("read", address, count))
            return type("Response", (), {"registers": [0], "isError": lambda self: False})()

        def write_register(self, *args):
            pytest.fail("Diagnostic action wrote COMMAND")

    backend = make_backend()
    backend._modbus_factory = lambda: ModbusClient("fake-host", transport=Transport())
    assert getattr(backend, action)()
    assert events == ["connect", ("read", 129, 1), "close"]


def test_refresh_preserves_camera_error_and_does_not_resume_uncertain_turn():
    backend = make_backend(observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, False)
    old = backend.modbus_client

    def lost_reply(cell):
        old.commands.append(cell)
        raise ModbusConnectionError("reply lost")

    old.write_command = lost_reply
    app.update()
    assert app.runtime.command_sent and app.runtime.state == RuntimeState.ERROR
    before = app.runtime.snapshot()
    backend.last_error = "CAMERA_CAPTURE_ERROR: unavailable"
    fresh = FakeModbus((0,))
    backend._modbus_factory = lambda: fresh
    assert app.reconnect_robot()
    finish(app)
    assert backend.robot_status == "LISTO"
    assert backend.last_error == "CAMERA_CAPTURE_ERROR: unavailable"
    assert app.runtime.snapshot() == before
    for _ in range(3):
        app.update()
    assert app.runtime.snapshot() == before
    assert app.snapshot().robot_status == "REQUIERE RECUPERACIÓN"  # Explicit cancellation/reset still required.
    assert not app.new_game(HARD, True)
    assert fresh.commands == [] and len(old.commands) == 1
    app.close()


def test_dashboard_unavailable_does_not_break_modbus(monkeypatch):
    def unavailable(*args, **kwargs):
        raise TimeoutError("29999 unavailable")

    monkeypatch.setattr("ur_tictactoe.communication.dashboard_client.socket.create_connection", unavailable)
    backend = make_backend(observer=RecordingObserver(physical()))
    backend._dashboard_client = DashboardClient("fake-host")
    backend.dashboard_enabled = True
    assert backend.refresh_status()
    assert backend.modbus_status == "CONECTADO" and backend.robot_status == "LISTO"
    assert backend.dashboard.availability == "NO DISPONIBLE"
    assert backend.dashboard.program_state == "DESCONOCIDO"
    assert backend.last_error is None
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, True)
    app.close()


def test_diagnostics_present_runtime_reads_without_extra_queries():
    client = FakeModbus((0, 0, 0, 1, 2))  # Startup, start guard, READY/send, BUSY, DONE.
    backend = make_backend(modbus=client, observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, False)
    for expected in ("READY", "BUSY", "DONE"):
        app.update()
        assert app.diagnostic_snapshot().controller_status == expected
    assert len(client.commands) == 1
    app.close()


def test_query_serialization_shutdown_and_no_automatic_moves():
    backend = make_backend()
    app = GameApplication(False, real_backend=backend)
    app.open()
    entered, release = Event(), Event()
    fresh = FakeModbus()

    def read():
        entered.set()
        assert release.wait(3)
        return 0

    fresh.read_status = read
    backend._modbus_factory = lambda: fresh
    try:
        assert app.refresh_status()
        assert entered.wait(1)
        assert not app.reconnect_robot()
        assert not app.reconnect_camera()
        assert not app.open_async()
        assert not app.new_game(HARD, False)
        app.update()
        assert backend.camera.read_calls == 0
        app.close()
        assert backend.camera.close_calls == 0
    finally:
        release.set()
        finish(app)
    assert backend.camera.close_calls == 1
    assert fresh.commands == []
    assert not app.refresh_status()


@pytest.mark.parametrize("state", [RuntimeState.WAITING_HUMAN, RuntimeState.WAITING_ROBOT,
                                   RuntimeState.ROBOT_BUSY, RuntimeState.VERIFYING_ROBOT,
                                   RuntimeState.ACKNOWLEDGING_ROBOT])
def test_diagnostics_do_not_interrupt_active_handshake(state):
    backend = make_backend(observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, True)
    app.runtime.state = state
    client = backend.modbus_client
    counts = client.connect_calls, client.close_calls
    assert not app.refresh_status()
    assert not app.reconnect_robot()
    assert counts == (client.connect_calls, client.close_calls)
    assert client.commands == []
    app.close()
