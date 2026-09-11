"""Explicit reset/GUI recovery with no sockets, camera or physical robot."""

from threading import Event, Thread

import pytest

from ur_tictactoe.communication import ModbusClient, ModbusConnectionError
from ur_tictactoe.communication.dashboard_client import DashboardSnapshot
from ur_tictactoe.communication.robot_recovery import BUSY_WARNING
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.help_content import start_explanation
from ur_tictactoe.game import HARD
from ur_tictactoe.runtime import RuntimeState
from test_real_backend import FakeModbus, RecordingObserver, make_backend, physical
from test_robot_recovery import finish


class FakeDashboard:
    def __init__(self):
        self.calls = 0
        self.close_calls = 0

    def close(self):
        self.close_calls += 1

    def snapshot(self):
        self.calls += 1
        return DashboardSnapshot("DISPONIBLE", "EJECUTANDO", "RUNNING", "fake")


def setup_recovery(statuses=(0, 0)):
    backend = make_backend(observer=RecordingObserver(physical()))
    backend._dashboard_client = FakeDashboard()
    app = GameApplication(False, real_backend=backend)
    assert app.open()
    app.update()
    fresh = FakeModbus(statuses)
    backend._modbus_factory = lambda: fresh
    return app, backend, fresh


@pytest.mark.parametrize("initial", [0, 2, 3])
def test_explicit_recovery_writes_only_one_zero_and_refreshes_all_statuses(initial):
    app, backend, fresh = setup_recovery((initial, 0))
    old = backend.modbus_client
    observer, observation = backend.observer, backend.last_observation
    camera_counts = backend.camera.open_calls, backend.camera.read_calls, backend.camera.close_calls
    backend._set_robot_error("MODBUS_CONNECTION_ERROR: old connection")
    app._last_error = backend.last_error
    assert app.recover_robot()
    finish(app)
    assert fresh.commands == [0]
    assert fresh.connect_calls == fresh.close_calls == 1
    assert old.close_calls == 2 and old.commands == []
    assert app.snapshot().robot_status == "LISTO"
    assert app.snapshot().last_error is backend.last_error is None
    assert backend.controller_status == "READY" and backend.modbus_status == "CONECTADO"
    assert app.robot_feedback == "ROBOT RECUPERADO · READY"
    assert backend._dashboard_client.calls == 1  # Also queried when optional refresh is off.
    assert app.diagnostic_snapshot().dashboard.program_state == "EJECUTANDO"
    assert backend.observer is observer and backend.last_observation is observation
    assert camera_counts == (backend.camera.open_calls, backend.camera.read_calls, backend.camera.close_calls)
    app.close()


def test_busy_aborts_without_any_write():
    app, backend, fresh = setup_recovery((1,))
    assert app.recover_robot()
    finish(app)
    assert fresh.commands == []
    assert fresh.close_calls == 1
    assert backend.controller_status == "BUSY" and app.snapshot().robot_status == "EN MOVIMIENTO"
    assert app.robot_feedback == BUSY_WARNING
    assert backend._dashboard_client.calls == 1
    app.close()


@pytest.mark.parametrize("statuses,commands", [((99,), []), ((2, 1), [0]), ((3, 99), [0])])
def test_unexpected_or_busy_response_never_retries(statuses, commands):
    app, backend, fresh = setup_recovery(statuses)
    assert not backend.recover_robot()
    assert fresh.commands == commands and fresh.close_calls == 1
    assert backend.robot_error
    app.close()


def test_recovery_timeout_only_polls_and_closes():
    app, backend, fresh = setup_recovery()
    fresh.read_status = lambda: 2
    clock = [0.0]
    def wait(seconds):
        clock[0] += seconds
    assert not backend.recover_robot(timeout=0.1, clock=lambda: clock[0], wait=wait)
    assert fresh.commands == [0] and fresh.close_calls == 1
    assert "No se recibió READY" in backend.robot_error
    assert backend.modbus_status == "CONECTADO"
    assert backend.robot_status == "REQUIERE RECUPERACIÓN"
    assert not backend.is_open
    app.close()


@pytest.mark.parametrize("stage", ["connect", "read_status", "clear_command", "close"])
def test_transport_failure_does_not_claim_recovered_or_retry(stage):
    app, backend, fresh = setup_recovery((2, 0))
    calls = []
    def fail(*args):
        calls.append(stage)
        raise ModbusConnectionError("lost reply")
    setattr(fresh, stage, fail)
    assert not backend.recover_robot()
    assert calls == [stage]
    assert backend.robot_status == "ERROR DE CONEXIÓN"
    assert not backend.is_open
    assert fresh.commands in ([], [0])
    app.close()


def test_uncertain_game_is_archived_cancelled_and_never_replayed(monkeypatch):
    app, backend, fresh = setup_recovery()
    old = backend.modbus_client
    backend._modbus_factory = lambda: old
    assert app.new_game(HARD, False)
    def lost_reply(cell):
        old.commands.append(cell)
        raise ModbusConnectionError("delivery uncertain")
    old.write_command = lost_reply
    app.update()
    previous = app.runtime.snapshot()
    def forbidden_request():
        pytest.fail("Recovery requested a new robot move")
    monkeypatch.setattr(app.session, "request_robot_move", forbidden_request)
    assert previous.pending_robot_move is not None and app.runtime.command_sent
    assert app.snapshot().robot_status == "ERROR DE CONEXIÓN"
    backend._modbus_factory = lambda: fresh
    assert app.recover_robot()
    finish(app)
    assert app.runtime is app.session is None
    assert app.cancelled_games[0].snapshot == previous
    assert app.cancelled_games[0].command_sent
    assert app.cancelled_games[0].cause == "delivery uncertain"
    assert "PARTIDA CANCELADA" in app.snapshot().action_status
    assert "REQUIERE NUEVA PARTIDA" in app.robot_feedback
    assert app.snapshot().robot_status == "LISTO" and app.snapshot().last_error is None
    assert "pending_robot_move" in app.diagnostic_snapshot().game_history[0]
    for _ in range(4):
        app.update()
    assert fresh.commands == [0] and old.commands == [previous.pending_robot_move]
    backend.observer.state = physical(previous.pending_robot_move)
    app.update()
    assert not app.new_game(HARD, True)
    assert app.snapshot().last_error == "BOARD_NOT_EMPTY"
    backend.observer.state = physical()
    app.update()
    assert app.new_game(HARD, True)  # Explicit, new session; board must be empty.
    assert app.runtime.state == RuntimeState.WAITING_HUMAN
    assert fresh.commands == [0]
    assert len(app.cancelled_games) == 1
    app.close()


def test_waiting_human_game_is_cancelled_even_when_recovery_fails():
    app, backend, fresh = setup_recovery((1,))
    old = backend.modbus_client
    backend._modbus_factory = lambda: old
    assert app.new_game(HARD, True)
    backend._modbus_factory = lambda: fresh
    assert app.recover_robot()
    finish(app)
    assert app.runtime is None and len(app.cancelled_games) == 1
    assert app.cancelled_games[0].snapshot.state == RuntimeState.WAITING_HUMAN
    assert fresh.commands == []
    app.close()


@pytest.mark.parametrize("state", [RuntimeState.WAITING_ROBOT, RuntimeState.ROBOT_BUSY,
                                   RuntimeState.VERIFYING_ROBOT, RuntimeState.ACKNOWLEDGING_ROBOT])
def test_recovery_cannot_interrupt_a_live_robot_turn(state):
    app, backend, fresh = setup_recovery()
    assert app.new_game(HARD, False)
    app.runtime.state = state
    before = app.runtime.snapshot()
    assert not app.recover_robot()
    assert app.runtime.snapshot() == before
    assert fresh.commands == [] and not app.cancelled_games
    if state == RuntimeState.ROBOT_BUSY:
        assert app.robot_feedback == BUSY_WARNING
    app.close()


@pytest.mark.parametrize("status", [1, 2, 3])
def test_start_reads_fresh_status_and_does_not_reset(status):
    app, backend, fresh = setup_recovery((status,))
    assert backend.controller_status == "READY"  # Cached startup evidence is insufficient.
    assert not app.new_game(HARD, False)
    assert fresh.connect_calls == fresh.close_calls == 1 and fresh.commands == []
    assert app.runtime is None
    if status in (2, 3):
        assert "Robot requiere recuperación" in start_explanation(app.snapshot())
        assert "REINICIAR SISTEMA" in start_explanation(app.snapshot())
    app.close()


def test_start_requires_connected_camera_without_reopening_it():
    app, backend, fresh = setup_recovery()
    backend.camera_status = "ERROR"
    assert not app.new_game(HARD, False)
    assert fresh.connect_calls == 0 and fresh.commands == []
    assert backend.camera.open_calls == 1
    app.close()


def test_success_preserves_non_transport_error_and_dashboard_is_independent():
    app, backend, fresh = setup_recovery()
    backend.last_error = "CAMERA_CAPTURE_ERROR: retained evidence"
    backend._dashboard_client.snapshot = lambda: DashboardSnapshot(detail="29999 unavailable")
    assert app.recover_robot()
    finish(app)
    assert app.snapshot().robot_status == "LISTO"
    assert app.snapshot().last_error == "CAMERA_CAPTURE_ERROR: retained evidence"
    assert backend.dashboard.availability == "NO DISPONIBLE"
    assert fresh.commands == [0]
    app.close()


def test_recovery_is_serialized_with_a_command_being_sent():
    app, backend, fresh = setup_recovery()
    assert app.new_game(HARD, False)
    entered, release = Event(), Event()
    def send(cell):
        fresh.commands.append(cell)
        entered.set()
        assert release.wait(3)
    fresh.write_command = send
    update_thread = Thread(target=app.update)
    outcomes = []
    recover_thread = Thread(target=lambda: outcomes.append(app.recover_robot()))
    try:
        update_thread.start()
        assert entered.wait(1)
        recover_thread.start()
    finally:
        release.set()
        update_thread.join(3)
        recover_thread.join(3)
    assert not update_thread.is_alive() and not recover_thread.is_alive()
    assert outcomes == [False]
    assert len(fresh.commands) == 1 and fresh.commands[0] in range(1, 10)
    app.close()


def test_recovery_adapter_writes_only_register128_zero():
    app, backend, _ = setup_recovery()
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
        def write_register(self, address, value):
            events.append(("write", address, value))
            return type("Response", (), {"isError": lambda self: False})()
    backend._modbus_factory = lambda: ModbusClient("fake-host", transport=Transport())
    assert backend.recover_robot()
    assert events == ["connect", ("read", 129, 1), ("write", 128, 0), ("read", 129, 1), "close"]
    app.close()
