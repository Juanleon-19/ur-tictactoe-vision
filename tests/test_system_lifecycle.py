"""Product restart and complete shutdown, using only fake devices."""
from threading import Event

import pytest

from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.game import HARD
from ur_tictactoe.runtime import RuntimeState
from test_explicit_robot_recovery import FakeDashboard, setup_recovery
from test_real_backend import RecordingObserver, physical, make_backend
from test_robot_recovery import finish


@pytest.mark.parametrize("status", [0, 2, 3])
def test_restart_cancels_pending_resets_observation_without_reopening_camera(status, monkeypatch):
    app, backend, fresh = setup_recovery()
    assert app.new_game(HARD, False)
    app.session.request_robot_move()
    pending = app.session.pending_robot_move
    assert pending is not None
    monkeypatch.setattr(app.session, "request_robot_move", lambda: pytest.fail("Pending move replayed"))
    previous = backend.observer
    fresh.statuses = [status, 0]
    assert app.restart_system()
    finish(app)
    assert app.session is app.runtime is None
    assert app.cancelled_games[0].snapshot.pending_robot_move == pending
    assert fresh.commands == [0]
    assert backend.observer is not previous and backend.last_observation is None
    assert backend.camera.open_calls == 1 and backend.camera.close_calls == 0
    assert backend._dashboard_client.calls == 1
    backend.observer = RecordingObserver(physical())
    for _ in range(3):
        app.update()
    assert app.robot_feedback == "SISTEMA LISTO"
    assert app.snapshot().robot_status == "LISTO"
    assert "PARTIDA CANCELADA" in app.snapshot().action_status
    assert fresh.commands == [0]
    app.shutdown_all(wait=True)


def test_busy_restart_cancels_local_runtime_without_reset_or_motion():
    app, backend, fresh = setup_recovery()
    assert app.new_game(HARD, False)
    app.runtime.state = RuntimeState.ROBOT_BUSY
    app.runtime.command_sent = True
    fresh.statuses = [1]
    previous = backend.observer
    assert app.restart_system()
    finish(app)
    assert app.runtime is app.session is None
    assert fresh.commands == []
    assert backend.observer is previous
    assert backend.camera.open_calls == 1 and backend.camera.close_calls == 0
    assert "Robot en movimiento" in app.robot_feedback and "parada física" in app.robot_feedback
    assert app.snapshot().robot_status == "EN MOVIMIENTO"
    assert backend._dashboard_client.calls == 1
    app.shutdown_all(wait=True)
    assert fresh.commands == []


def test_restart_reports_camera_failure_and_requires_new_empty_board():
    app, backend, fresh = setup_recovery()
    backend.camera_status = "ERROR"
    assert app.restart_system()
    finish(app)
    assert "RECONECTAR CÁMARA" in app.robot_feedback
    assert backend.camera.open_calls == 1
    backend.camera_status = "CONECTADA"
    backend.observer = RecordingObserver(physical(5))
    app.update()
    assert "Retire las fichas" in app.robot_feedback
    assert not app.new_game(HARD, True)
    assert fresh.commands == [0]
    app.shutdown_all(wait=True)


def test_restart_reports_first_capture_failure_without_reopening():
    app, backend, fresh = setup_recovery()
    assert app.restart_system()
    finish(app)
    def fail_read():
        raise RuntimeError("USB unavailable")
    backend.camera.read = fail_read
    app.update()
    assert "RECONECTAR CÁMARA" in app.robot_feedback
    assert backend.camera.open_calls == 1 and backend.camera.close_calls == 0
    assert fresh.commands == [0]
    app.shutdown_all(wait=True)


@pytest.mark.parametrize("broken", [None, "camera", "modbus", "dashboard"])
def test_shutdown_attempts_every_close_even_after_exception_and_is_idempotent(broken):
    app, backend, fresh = setup_recovery()
    events = []
    def close(name):
        def action():
            events.append(name)
            if name == broken:
                raise RuntimeError("test release failure")
        return action
    backend.camera.close = close("camera")
    backend.modbus_client.close = close("modbus")
    backend._dashboard_client.close = close("dashboard")
    app.shutdown_all(wait=True)
    assert app.shutdown_complete
    assert events == ["camera", "modbus", "dashboard"]
    assert bool(app.shutdown_error) == bool(broken)
    app.shutdown_all(wait=True)
    assert events == ["camera", "modbus", "dashboard"]
    assert not app.open_async() and not app.reconnect_camera()
    assert not app.apply_camera(1, "DSHOW") and not app.restart_system()
    assert not app.refresh_status() and not app.new_game(HARD, False)
    assert not app.set_aruco_profile("robust_glare")
    assert fresh.commands == []


@pytest.mark.parametrize("failing_open", [False, True])
def test_shutdown_waits_for_camera_worker_then_releases_all_resources(failing_open):
    backend = make_backend()
    backend._dashboard_client = FakeDashboard()
    app = GameApplication(False, real_backend=backend)
    entered, release = Event(), Event()
    def open_camera():
        backend.camera.open_calls += 1
        entered.set()
        assert release.wait(3)
        if failing_open:
            raise RuntimeError("test driver failure")
    backend.camera.open = open_camera
    try:
        assert app.open_async() and entered.wait(1)
        assert not app.open_async() and not app.reconnect_camera()
        app.shutdown_all()
        assert not app.shutdown_complete
        assert not app.open_async() and not app.apply_camera(2, "MSMF")
    finally:
        release.set()
        app.shutdown_all(wait=True)
    assert app.shutdown_complete and not app._camera_worker.is_alive()
    assert not app._shutdown_worker.is_alive()
    assert backend.camera.open_calls == backend.camera.close_calls == 1
    assert backend.modbus_client.close_calls >= 1 and backend.modbus_client.commands == []
    assert backend._dashboard_client.close_calls == 1


def test_shutdown_waits_for_robot_query_worker_without_writing():
    app, backend, fresh = setup_recovery()
    entered, release = Event(), Event()
    def status():
        entered.set()
        assert release.wait(3)
        return 0
    fresh.read_status = status
    try:
        assert app.refresh_status() and entered.wait(1)
        app.shutdown_all()
        assert not app.shutdown_complete
    finally:
        release.set()
        app.shutdown_all(wait=True)
    assert app.shutdown_complete and not app._robot_worker.is_alive()
    assert fresh.commands == [] and fresh.close_calls >= 1
    assert backend.camera.close_calls == backend._dashboard_client.close_calls == 1


def test_shutdown_busy_warns_and_never_acknowledges():
    app, backend, fresh = setup_recovery()
    assert app.new_game(HARD, False)
    app.runtime.state = RuntimeState.ROBOT_BUSY
    app.runtime.command_sent = True
    assert "no lo detiene" in app.shutdown_warning
    app.shutdown_all(wait=True)
    assert app.runtime is app.session is None and app.shutdown_complete
    assert fresh.commands == []


def test_simulation_restart_cancels_without_creating_hardware():
    app = GameApplication(True)
    assert app.new_game(HARD, False)
    assert app.restart_system()
    assert app.runtime is app.session is app.real_backend is None
    assert app.robot_feedback == "SISTEMA LISTO"
    app.shutdown_all(wait=True)
