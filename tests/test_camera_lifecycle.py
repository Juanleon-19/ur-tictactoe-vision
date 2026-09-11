"""Capture timing and ownership without a physical camera."""

from threading import Event, Thread

import pytest

from ur_tictactoe.config import CameraConfig
from ur_tictactoe.vision.camera import Camera
from ur_tictactoe.desktop.application import GameApplication
from test_real_backend import make_backend


class Capture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def set(self, *args):
        return True

    def getBackendName(self):
        return "FAKE"

    def read(self):
        return True, object()

    def release(self):
        self.released = True


def test_open_and_first_frame_metrics(monkeypatch):
    clock = [10.0]
    captures = []

    class TimedCapture(Capture):
        def __init__(self, index, backend):
            super().__init__()
            assert index == 2
            clock[0] += 2
            captures.append(self)

        def set(self, *args):
            clock[0] += 0.5

        def read(self):
            clock[0] += 0.25
            return super().read()

    monkeypatch.setattr("ur_tictactoe.vision.camera.cv2.VideoCapture", TimedCapture)
    monkeypatch.setattr("ur_tictactoe.vision.camera.monotonic", lambda: clock[0])
    camera = Camera(CameraConfig(index=2))
    camera.open()
    assert camera.capture_open_seconds == 2
    assert camera.configure_seconds == 1.5
    assert camera.camera_open_seconds == 3.5
    assert camera.first_frame_seconds is None
    assert camera.effective_backend == "FAKE"
    camera.open()
    assert len(captures) == 1
    clock[0] += 5
    camera.read()
    assert camera.first_frame_seconds == 5.25
    assert camera.first_frame_read_seconds == 0.25
    camera.read()
    assert camera.first_frame_seconds == 5.25
    camera.close()
    assert captures[0].released
    camera.open()
    assert camera.first_frame_seconds is None
    assert len(captures) == 2
    camera.close()


@pytest.mark.parametrize("next_operation", ["open", "close"])
def test_open_is_serialized_with_open_and_release(monkeypatch, next_operation):
    entered, release, second_started, second_finished = Event(), Event(), Event(), Event()
    captures, errors = [], []

    def create(*args):
        capture = Capture()
        captures.append(capture)
        entered.set()
        assert release.wait(3)
        return capture

    monkeypatch.setattr("ur_tictactoe.vision.camera.cv2.VideoCapture", create)
    camera = Camera(CameraConfig())

    def operate(name):
        try:
            getattr(camera, name)()
        except Exception as exc:
            errors.append(exc)

    first = Thread(target=lambda: operate("open"))

    def second_operation():
        second_started.set()
        operate(next_operation)
        second_finished.set()

    second = Thread(target=second_operation)
    try:
        first.start()
        assert entered.wait(1)
        assert camera.opening_seconds is not None
        second.start()
        assert second_started.wait(1)
        assert not second_finished.wait(0.05)
        assert len(captures) == 1 and not captures[0].released
    finally:
        release.set()
        first.join(3)
        second.join(3)
    assert not errors
    assert not first.is_alive() and not second.is_alive()
    assert len(captures) == 1
    assert captures[0].released == (next_operation == "close")
    camera.close()


def test_failed_configuration_releases_capture_and_reports_timing(monkeypatch):
    capture = Capture()

    def bad_set(*args):
        raise RuntimeError("driver configuration failed")

    capture.set = bad_set
    monkeypatch.setattr("ur_tictactoe.vision.camera.cv2.VideoCapture", lambda *args: capture)
    camera = Camera(CameraConfig())
    with pytest.raises(RuntimeError, match="configuration failed"):
        camera.open()
    assert capture.released and camera._capture is None
    assert camera.camera_open_seconds is not None
    assert camera.opening_seconds is None


@pytest.mark.parametrize("status", ["CONECTADA", "ERROR"])
def test_detect_skips_owned_camera_even_for_different_backend(monkeypatch, status):
    backend = make_backend()
    app = GameApplication(False, real_backend=backend)
    app.open()
    backend.camera_status = status
    calls = []
    monkeypatch.setattr("ur_tictactoe.desktop.camera_controls.detect_local_cameras",
                        lambda selected, known: calls.append((selected, known)) or [known])
    assert app.detect_cameras("DSHOW")
    app._camera_worker.join(3)
    assert calls == [("DSHOW", backend.camera_config.index)]
    assert backend.camera.open_calls == 1 and backend.camera.close_calls == 0
    app.close()


def test_diagnostic_snapshot_exports_camera_metrics():
    backend = make_backend()
    backend.camera.camera_open_seconds = 3.5
    backend.camera.first_frame_seconds = 0.25
    backend.camera.effective_backend = "FAKE"
    snapshot = backend.diagnostic_snapshot()
    assert snapshot.camera_open_seconds == 3.5 and snapshot.first_frame_seconds == 0.25
    assert snapshot.backend == "AUTO" and snapshot.camera_index == 0
    assert snapshot.effective_backend == "FAKE"


def test_release_exception_drops_local_handle(monkeypatch):
    capture = Capture()
    def fail_release():
        capture.released = True
        raise RuntimeError("release failed")
    capture.release = fail_release
    monkeypatch.setattr("ur_tictactoe.vision.camera.cv2.VideoCapture", lambda *args: capture)
    camera = Camera(CameraConfig())
    camera.open()
    with pytest.raises(RuntimeError, match="release failed"):
        camera.close()
    assert capture.released and camera._capture is None
    camera.close()


@pytest.mark.parametrize("operation", ["reconnect", "apply"])
def test_camera_replacement_closes_before_factory_and_backend_change(operation):
    backend = make_backend()
    backend.open()
    old = backend.camera
    events = []
    original_close = old.close
    def close():
        events.append(("close", backend.camera_config.backend))
        original_close()
    old.close = close
    def factory(config):
        assert old.close_calls == 1
        events.append(("create", config.backend))
        from test_real_backend import FakeCamera
        return FakeCamera(config)
    backend._camera_factory = factory
    if operation == "apply":
        assert backend.apply_camera(2, "DSHOW")
    else:
        assert backend.reconnect_camera()
    assert events == [("close", "AUTO"), ("create", "DSHOW" if operation == "apply" else "AUTO")]
    assert backend.camera.open_calls == 1
    backend.close()
