"""Operator controls exercise fake devices only; no robot or camera required."""

from dataclasses import replace
import json
import os
from threading import Event

import cv2
import numpy as np
import pytest

from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.camera_controls import detect_local_cameras
from ur_tictactoe.desktop.commissioning_status import latest_commissioning
from ur_tictactoe.desktop.diagnostics import diagnostic_text, illumination_status
from ur_tictactoe.desktop.help_content import BOARD_MAP, SECTIONS, help_text, start_explanation
from ur_tictactoe.game import HARD
from ur_tictactoe.runtime import RuntimeState
from test_real_backend import FakeCamera, RecordingObserver, make_backend, physical


def finish(app):
    app._camera_worker.join(timeout=3)
    assert not app.camera_busy


@pytest.mark.parametrize("operation", ["apply", "reconnect", "reset"])
def test_camera_lifecycle_preserves_robot_and_reacquires(operation):
    backend = make_backend(observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    camera, detector, observer = backend.camera, backend.detector, backend.observer
    if operation == "apply":
        assert app.apply_camera(2, "DSHOW")
        finish(app)
        assert backend.camera_config.index == 2
        assert backend.camera_config.backend == "DSHOW"
    elif operation == "reconnect":
        assert app.reconnect_camera()
        finish(app)
    else:
        assert app.reset_board_observation()
        assert "Observación reiniciada" in app.camera_feedback
    assert backend.modbus_client.connect_calls == 1
    assert backend.modbus_client.close_calls == 0
    assert backend.modbus_client.commands == []
    assert camera.open_calls == (1 if operation == "reset" else 2)
    assert camera.close_calls == (0 if operation == "reset" else 1)
    assert backend.detector is detector
    assert backend.observer is not observer
    assert backend.last_observation is app._last_observation is None
    snapshot = app.diagnostic_snapshot()
    assert snapshot.frame is None and snapshot.visible_ids == ()
    assert app.snapshot().board_status == "ESPERANDO TABLERO"
    assert not app.new_game(HARD, True)
    app.close()


@pytest.mark.parametrize("state", [RuntimeState.WAITING_HUMAN, RuntimeState.WAITING_ROBOT,
                                    RuntimeState.ROBOT_BUSY, RuntimeState.VERIFYING_ROBOT,
                                    RuntimeState.ERROR])
def test_controls_blocked_during_physical_game(state):
    backend = make_backend(observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, True)
    app.runtime.state = state
    observer = backend.observer
    assert not app.apply_camera(1, "MSMF")
    assert not app.reconnect_camera()
    assert not app.reset_board_observation()
    assert not app.detect_cameras("AUTO")
    assert backend.observer is observer
    assert backend.camera.close_calls == 0
    assert backend.modbus_client.connect_calls == 1
    app.close()


def test_slow_camera_keeps_ui_commands_responsive_and_closes_after_completion():
    backend = make_backend()
    app = GameApplication(False, real_backend=backend)
    app.open()
    entered, release = Event(), Event()

    class SlowCamera(FakeCamera):
        def open(self):
            entered.set()
            assert release.wait(3)
            super().open()

    camera = SlowCamera(None)
    backend._camera_factory = lambda config: camera
    try:
        assert app.apply_camera(1, "MSMF")
        assert entered.wait(1)
        assert app.camera_busy
        assert app.camera_feedback == "Inicializando cámara..."
        assert not app.reconnect_camera()
        assert not app.set_aruco_profile("default")
        assert not app.new_game(HARD, True)
        app.update()
        assert camera.read_calls == 0
        assert backend.modbus_client.connect_calls == 1
        app.close()
        assert camera.close_calls == 0
    finally:
        release.set()
        finish(app)
    assert camera.close_calls == 1
    assert backend.modbus_client.close_calls == 1


def test_reconnect_failure_then_recovery_preserves_modbus():
    backend = make_backend()
    app = GameApplication(False, real_backend=backend)
    app.open()
    backend.camera.open_error = RuntimeError("USB unavailable")
    assert app.reconnect_camera()
    finish(app)
    assert backend.camera_status == "ERROR"
    assert "CAMERA_OPEN_ERROR" in app.camera_feedback
    assert backend.robot_status == "LISTO"
    backend.camera.open_error = None
    assert app.reconnect_camera()
    finish(app)
    assert backend.camera_status == "CONECTADA"
    assert app.snapshot().last_error is None
    assert backend.modbus_client.connect_calls == 1
    app.close()


def test_discovery_releases_each_capture_even_on_driver_error(monkeypatch):
    captures = []

    class Capture:
        def __init__(self):
            self.released = False
            captures.append(self)

        def open(self, index, backend):
            assert all(c.released for c in captures[:-1])
            self.index = index
            assert backend == cv2.CAP_DSHOW
            if index == 3:
                raise cv2.error("driver error")

        def isOpened(self):
            return self.index in (0, 1)

        def release(self):
            self.released = True

    monkeypatch.setattr(cv2, "VideoCapture", Capture)
    assert detect_local_cameras("DSHOW") == [0, 1]
    assert len(captures) == 6
    assert all(c.released for c in captures)
    captures.clear()
    assert detect_local_cameras("DSHOW", known_open=1) == [0, 1]
    assert len(captures) == 5


def test_detection_does_not_change_session_configuration(monkeypatch):
    backend = make_backend()
    app = GameApplication(False, real_backend=backend)
    app.open()
    config = backend.camera_config
    monkeypatch.setattr("ur_tictactoe.desktop.camera_controls.detect_local_cameras",
                        lambda backend, known: [1, 2])
    assert app.detect_cameras("AUTO")
    finish(app)
    assert app.detected_cameras == ["Camera 1", "Camera 2"]
    assert backend.camera_config == config
    assert backend.camera.close_calls == 0
    assert backend.modbus_client.connect_calls == 1
    app.close()


def test_diagnostics_and_illumination_preserve_productive_frame(monkeypatch):
    times = iter((1.0, 1.1))
    monkeypatch.setattr("ur_tictactoe.desktop.real_backend.monotonic", lambda: next(times))
    backend = make_backend(observer=RecordingObserver(physical()))
    frame = np.full((720, 1280, 3), 255, dtype=np.uint8)
    original = frame.copy()
    backend.camera.frame = frame
    backend.detector.ids = (10, 11, 18)
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    app.update()
    snapshot = app.diagnostic_snapshot()
    assert backend.detector.frames[0] is frame
    np.testing.assert_array_equal(frame, original)
    assert snapshot.illumination == "POSIBLE REFLEJO / SOBREEXPOSICIÓN"
    assert illumination_status(np.zeros_like(frame)) == "CORRECTA"
    assert snapshot.resolution == (1280, 720) and snapshot.fps > 0
    text = diagnostic_text(snapshot, app.snapshot().board_status, "INTERNAL_CODE")
    for expected in ("0 · AUTO", "1280×720", "3/9", "10, 11, 18", "12, 13, 14, 15, 16, 17",
                     "Tablero: LISTO", "INTERNAL_CODE", "ILUMINACIÓN"):
        assert expected in text
    app.close()


def write_report(path, rows, time):
    path.write_text(json.dumps({"results": rows}), encoding="utf-8")
    os.utime(path, (time, time))


def test_latest_valid_report_is_read_only_and_does_not_merge(tmp_path):
    older, newest = [tmp_path / f"commissioning_{i}.json" for i in (1, 2)]
    write_report(older, [{"test": "C1", "status": "PASS"}], 100)
    write_report(newest, [{"test": "C4", "status": "PASS"}], 200)
    before = newest.read_bytes()
    report = latest_commissioning(tmp_path)
    assert report.source == newest.name
    assert report.results == {"C4": "PASS"}
    assert newest.read_bytes() == before
    newest.write_text("{corrupt", encoding="utf-8")
    assert latest_commissioning(tmp_path).results == {"C1": "PASS"}


@pytest.mark.parametrize("content", [None, "{broken", "[]", '{"results": []}',
                                    '{"results": [{"test": "C1", "status": "invented"}]}'])
def test_missing_or_invalid_report(tmp_path, content):
    if content is not None:
        (tmp_path / "commissioning_bad.json").write_text(content, encoding="utf-8")
    assert latest_commissioning(tmp_path) is None


def test_contextual_help_map_and_evidence():
    snapshot = GameApplication(True).snapshot()
    snapshot = replace(snapshot, simulation=False, camera_status="NO CONECTADA",
                       robot_status="NO CONFIGURADO", board_status="NO LISTO")
    text = help_text("Solucionar problema", snapshot, None)
    for expected in ("USB", "detectar cámaras", "retirar manos", "IDs faltantes", "subred", "C6"):
        assert expected in text
    for i in range(1, 10):
        assert f"CELL{i}" in BOARD_MAP and f"ID{i + 9}" in BOARD_MAP
    assert "CELL1  CELL2  CELL3\nID10     ID11     ID12" in BOARD_MAP
    assert "NO SE PUEDE INICIAR" in start_explanation(snapshot)
    assert "✕ Robot conectado" in start_explanation(snapshot)
    checklist = help_text("Puesta en marcha", snapshot, None)
    assert "PASS" not in checklist
    assert "Sin resultados" in checklist
    for section in SECTIONS:
        assert help_text(section, snapshot, None)
    assert "COMMAND0" in help_text("Acerca del sistema", snapshot, None)
    assert "NO debe mover robot" in help_text("Commissioning", snapshot, None)
