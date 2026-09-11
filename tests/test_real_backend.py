from __future__ import annotations

from dataclasses import dataclass

import pytest
import numpy as np

from ur_tictactoe.communication import (
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    ModbusConnectionError,
)
from ur_tictactoe.config import ArucoConfig, CameraConfig, UIConfig, VisionConfig
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.real_backend import RealGameBackend
from ur_tictactoe.game import HARD
from ur_tictactoe.runtime import RuntimeState
from ur_tictactoe.vision.aruco import DetectionResult
from ur_tictactoe.vision.board_observer import (
    BoardObserver,
    CellState,
    ObserverConfig,
    PhysicalBoardState,
)


def physical(
    *occupied: int, ready: bool = True, uncertain: tuple[int, ...] = ()
) -> PhysicalBoardState:
    cells = {
        cell: (
            CellState.UNCERTAIN
            if cell in uncertain
            else CellState.OCCUPIED
            if cell in occupied
            else CellState.FREE
        )
        for cell in range(1, 10)
    }
    return PhysicalBoardState(cells, {}, ready, 3, {})


class FakeCamera:
    def __init__(self, _config: object, open_error: Exception | None = None) -> None:
        self.open_calls = 0
        self.read_calls = 0
        self.close_calls = 0
        self.open_error = open_error
        self.frame = object()

    def open(self) -> None:
        self.open_calls += 1
        if self.open_error:
            raise self.open_error

    def read(self) -> object:
        self.read_calls += 1
        return self.frame

    def close(self) -> None:
        self.close_calls += 1


class FakeModbus:
    def __init__(
        self,
        statuses: tuple[int, ...] = (),
        connect_error: Exception | None = None,
    ) -> None:
        self.statuses = list(statuses)
        self.connect_error = connect_error
        self.connect_calls = 0
        self.close_calls = 0
        self.commands: list[int] = []

    def connect(self) -> None:
        self.connect_calls += 1
        if self.connect_error:
            raise self.connect_error

    def close(self) -> None:
        self.close_calls += 1

    def read_status(self) -> int:
        return self.statuses.pop(0) if self.statuses else STATUS_READY

    def write_command(self, cell: int) -> None:
        self.commands.append(cell)

    def clear_command(self) -> None:
        self.commands.append(0)


class FakeDetector:
    def __init__(self, ids: tuple[int, ...] = ()) -> None:
        self.ids = ids
        self.frames: list[object] = []

    def detect(self, frame: object) -> DetectionResult:
        self.frames.append(frame)
        return DetectionResult((), self.ids)


class RecordingObserver:
    def __init__(self, state: PhysicalBoardState | None = None) -> None:
        self.state = state or physical(ready=False, uncertain=tuple(range(1, 10)))
        self.visible: list[set[int]] = []

    def update(self, visible_ids: set[int]) -> PhysicalBoardState:
        self.visible.append(visible_ids)
        return self.state


def vision_config() -> VisionConfig:
    return VisionConfig(CameraConfig(), ArucoConfig(), UIConfig(), ObserverConfig())


def make_backend(
    camera: FakeCamera | None = None,
    detector: FakeDetector | None = None,
    observer: RecordingObserver | None = None,
    modbus: FakeModbus | None = None,
) -> RealGameBackend:
    camera = camera or FakeCamera(None)
    return RealGameBackend(
        vision_config(),
        "robot",
        camera_factory=lambda _config: camera,
        detector=detector or FakeDetector(),
        observer=observer or RecordingObserver(),
        modbus_client=modbus or FakeModbus(),
    )


def test_constructing_backend_does_not_open_devices() -> None:
    camera = FakeCamera(None)
    modbus = FakeModbus()
    make_backend(camera=camera, modbus=modbus)
    assert camera.open_calls == 0
    assert modbus.connect_calls == 0


def test_diagnostic_snapshot_reuses_single_capture_and_detection() -> None:
    camera = FakeCamera(None)
    camera.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detector = FakeDetector(tuple(range(10, 19)))
    observer = RecordingObserver(physical(2, uncertain=(9,)))
    backend = make_backend(camera=camera, detector=detector, observer=observer)
    backend.open()
    backend.tick()
    for _ in range(3):
        snapshot = backend.diagnostic_snapshot()
        assert snapshot.profile == "robust"
        assert snapshot.visible_ids == tuple(range(10, 19))
        assert snapshot.resolution == (1280, 720)
        assert snapshot.cells[0] == CellState.FREE
        assert snapshot.cells[1] == CellState.OCCUPIED
        assert snapshot.cells[8] == CellState.UNCERTAIN
        assert snapshot.frame is not None
    assert camera.open_calls == camera.read_calls == len(detector.frames) == 1


def test_diagnostic_snapshot_without_camera_or_frame() -> None:
    camera = FakeCamera(None, RuntimeError("absent"))
    backend = make_backend(camera=camera)
    assert backend.diagnostic_snapshot().frame is None
    backend.open()
    backend.tick()
    snapshot = backend.diagnostic_snapshot()
    assert snapshot.camera_status == "ERROR"
    assert snapshot.frame is None
    assert snapshot.visible_ids == ()
    assert snapshot.cells == (CellState.UNCERTAIN,) * 9
    assert camera.read_calls == 0


def test_simulated_diagnostics_never_open_hardware() -> None:
    app = GameApplication(simulation=True)
    assert app.diagnostic_snapshot().frame is None
    assert app.real_backend is None


def test_open_opens_camera_and_modbus() -> None:
    camera = FakeCamera(None)
    modbus = FakeModbus()
    backend = make_backend(camera=camera, modbus=modbus)
    assert backend.open()
    assert camera.open_calls == modbus.connect_calls == 1


def test_close_releases_both_resources_and_is_idempotent() -> None:
    camera = FakeCamera(None)
    modbus = FakeModbus()
    backend = make_backend(camera=camera, modbus=modbus)
    backend.open()
    backend.close()
    backend.close()
    assert camera.close_calls == 1
    assert modbus.close_calls == 2  # Availability probe, then final cleanup.


def test_camera_open_failure_is_reported_without_blocking_modbus_attempt() -> None:
    camera = FakeCamera(None, RuntimeError("camera unavailable"))
    modbus = FakeModbus()
    backend = make_backend(camera=camera, modbus=modbus)
    assert not backend.open()
    assert backend.camera_status == "ERROR"
    assert modbus.connect_calls == 1
    assert "CAMERA_OPEN_ERROR" in (backend.last_error or "")


def test_modbus_failure_is_reported_while_camera_remains_available() -> None:
    camera = FakeCamera(None)
    modbus = FakeModbus(connect_error=ModbusConnectionError("offline"))
    backend = make_backend(camera=camera, modbus=modbus)
    assert not backend.open()
    assert backend.camera_status == "CONECTADA"
    assert backend.robot_status == "ERROR DE CONEXIÓN"
    assert "MODBUS_CONNECTION_ERROR" in (backend.last_error or "")


def test_detected_frame_reaches_board_observer() -> None:
    detector = FakeDetector((10, 11, 18))
    observer = RecordingObserver(physical())
    backend = make_backend(detector=detector, observer=observer)
    backend.open()
    assert backend.tick() == observer.state
    assert detector.frames == [backend.camera.frame]
    assert observer.visible == [{10, 11, 18}]


@dataclass
class StubBackend:
    observation: PhysicalBoardState | None
    modbus_client: FakeModbus
    is_open: bool = True
    camera_status: str = "CONECTADA"
    robot_status: str = "LISTO"
    last_error: str | None = None
    open_calls: int = 0
    close_calls: int = 0

    def open(self) -> bool:
        self.open_calls += 1
        return self.is_open

    def tick(self) -> PhysicalBoardState | None:
        return self.observation

    def refresh_status(self) -> bool:
        return self.is_open

    def close(self) -> None:
        self.close_calls += 1


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (physical(ready=False, uncertain=tuple(range(1, 10))), "BOARD_NOT_READY"),
        (physical(ready=True, uncertain=(1,)), "BOARD_UNCERTAIN"),
        (physical(4), "BOARD_NOT_EMPTY"),
    ],
)
def test_invalid_physical_board_does_not_start_game(
    state: PhysicalBoardState, reason: str
) -> None:
    backend = StubBackend(state, FakeModbus())
    app = GameApplication(False, real_backend=backend)
    app.update()
    assert not app.new_game(HARD, True)
    assert app.snapshot().last_error == reason


def test_ready_empty_board_starts_real_game() -> None:
    backend = StubBackend(physical(), FakeModbus())
    app = GameApplication(False, real_backend=backend)
    app.update()
    assert app.new_game(HARD, True)
    assert app.snapshot().runtime_state == RuntimeState.WAITING_HUMAN


def test_real_observation_plays_human_move() -> None:
    backend = StubBackend(physical(), FakeModbus())
    app = GameApplication(False, real_backend=backend)
    app.update()
    app.new_game(HARD, True)
    backend.observation = physical(4)
    app.update()
    assert app.session.board.cell(4) == app.session.human
    assert app.runtime.state == RuntimeState.WAITING_ROBOT


def test_real_robot_handshake_waits_for_correct_visual_verification() -> None:
    modbus = FakeModbus((STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_READY))
    backend = StubBackend(physical(), modbus)
    app = GameApplication(False, real_backend=backend)
    app.update()
    assert app.new_game(HARD, False)

    app.update()
    expected = app.session.pending_robot_move
    assert modbus.commands == [expected]
    incorrect = next(cell for cell in range(1, 10) if cell != expected)
    backend.observation = physical(incorrect)
    app.update()
    assert app.runtime.state == RuntimeState.ROBOT_BUSY
    assert app.session.board.cell(incorrect) is None
    app.update()
    assert app.runtime.state == RuntimeState.VERIFYING_ROBOT
    app.update()
    assert app.session.pending_robot_move == expected
    assert modbus.commands == [expected]

    backend.observation = physical(expected)
    app.update()
    assert app.session.board.cell(expected) == app.session.robot
    assert app.session.pending_robot_move is None
    assert modbus.commands == [expected, 0]
    assert app.runtime.state == RuntimeState.ACKNOWLEDGING_ROBOT
    assert not app.new_game(HARD, True)
    app.update()
    assert app.runtime.state == RuntimeState.WAITING_HUMAN
    assert modbus.connect_calls == modbus.close_calls == 1


def test_real_lost_command_reply_blocks_new_game_and_preserves_pending_evidence():
    modbus = FakeModbus((STATUS_READY,))
    backend = StubBackend(physical(), modbus)
    app = GameApplication(False, real_backend=backend)
    app.update()
    assert app.new_game(HARD, False)
    def lost_reply(cell):
        modbus.commands.append(cell)
        raise ModbusConnectionError("test reply lost")
    modbus.write_command = lost_reply
    app.update()
    pending = app.session.pending_robot_move
    assert app.runtime.state == RuntimeState.ERROR
    assert not app.new_game(HARD, True)
    assert app.session.pending_robot_move == pending
    assert modbus.commands == [pending]
    assert modbus.close_calls == 1


def test_real_modbus_error_stops_runtime() -> None:
    backend = StubBackend(physical(), FakeModbus((STATUS_ERROR,)))
    app = GameApplication(False, real_backend=backend)
    app.update()
    app.new_game(HARD, False)
    app.update()
    assert app.runtime.state == RuntimeState.ERROR
    assert app.snapshot().robot_status == "REQUIERE RECUPERACIÓN"


def test_real_backend_default_observer_uses_cell_history(monkeypatch) -> None:
    from ur_tictactoe.desktop.application import AppConfig
    import ur_tictactoe.vision.board_observer as observer_module

    assert AppConfig().aruco_profile == "robust"
    backend = RealGameBackend(
        vision_config(), "test-host",
        camera_factory=FakeCamera, modbus_client=FakeModbus(),
    )
    assert backend.detector.profile == "robust"
    backend.detector = FakeDetector(tuple(range(10, 19)))
    clock = iter((0.0, 0.3, 0.6))
    monkeypatch.setattr(observer_module.time, "monotonic", lambda: next(clock))
    backend.open()
    for _ in range(3):
        state = backend.tick()
    assert state.ready
    assert state.free_cells == frozenset(range(1, 10))
    backend.close()


def test_real_backend_allows_diagnostic_default_profile() -> None:
    backend = RealGameBackend(
        vision_config(), "test-host", aruco_profile="default",
        camera_factory=FakeCamera, modbus_client=FakeModbus(),
    )
    assert backend.detector.profile == "default"


def test_real_backend_accepts_glare_profile_without_opening_hardware():
    backend = RealGameBackend(
        vision_config(), "test-host", aruco_profile="robust_glare",
        camera_factory=FakeCamera, modbus_client=FakeModbus(),
    )
    assert backend.detector.profile == "robust_glare"
    assert backend.diagnostic_snapshot().profile == "robust_glare"


@pytest.mark.parametrize("profile", ["default", "robust", "robust_glare"])
def test_hot_profile_replaces_vision_only_and_reacquires(profile, monkeypatch):
    import ur_tictactoe.vision.board_observer as observer_module

    camera = FakeCamera(None)
    camera.frame = np.zeros((48, 64, 3), dtype=np.uint8)
    backend = make_backend(camera=camera, detector=FakeDetector(tuple(range(10, 19))),
                           observer=RecordingObserver(physical(5)))
    app = GameApplication(False, real_backend=backend)
    assert app.open()
    app.update()
    old_detector, old_observer = backend.detector, backend.observer
    modbus = backend.modbus_client
    assert backend.diagnostic_snapshot().visible_ids
    assert app.set_aruco_profile(profile)
    assert backend.detector is not old_detector
    assert backend.detector.profile == profile
    assert isinstance(backend.observer, BoardObserver)
    assert backend.observer is not old_observer
    assert backend.observer.config == vision_config().observer
    assert not backend.observer.state.ready
    assert backend.last_observation is None
    snapshot = backend.diagnostic_snapshot()
    assert snapshot.profile == profile
    assert snapshot.visible_ids == () and snapshot.frame is None
    assert snapshot.cells == (CellState.UNCERTAIN,) * 9
    assert app.snapshot().board_status == "ESPERANDO TABLERO"
    assert app.config.aruco_profile == "robust"
    assert backend.camera is camera and backend.modbus_client is modbus
    assert backend.is_open
    assert camera.open_calls == modbus.connect_calls == 1
    assert camera.close_calls == 0
    assert modbus.close_calls == 1  # No socket is retained while waiting for a game.
    assert modbus.commands == []
    # Subsequent ticks use the replacement detector and normal temporal observer.
    monkeypatch.setattr(backend.detector, "detect", FakeDetector(tuple(range(10, 19))).detect)
    clock = iter((0.0, 0.3, 0.6))
    monkeypatch.setattr(observer_module.time, "monotonic", lambda: next(clock))
    for _ in range(3):
        app.update()
    assert app.snapshot().board_status == "LISTO"
    assert backend.diagnostic_snapshot().frame is not None
    assert camera.open_calls == modbus.connect_calls == 1
    app.close()


def test_invalid_profile_preserves_backend_and_ui_safe_rejection():
    backend = make_backend()
    detector, observer = backend.detector, backend.observer
    with pytest.raises(ValueError):
        backend.set_aruco_profile("invalid")
    app = GameApplication(False, real_backend=backend)
    assert not app.set_aruco_profile("invalid")
    assert app.profile_change_error == "Perfil de visión no válido."
    assert backend.detector is detector and backend.observer is observer
    assert backend.aruco_profile == "robust"


@pytest.mark.parametrize("state", [RuntimeState.WAITING_HUMAN, RuntimeState.WAITING_ROBOT,
                                  RuntimeState.ROBOT_BUSY, RuntimeState.VERIFYING_ROBOT,
                                  RuntimeState.ERROR])
def test_profile_change_blocked_during_real_game(state):
    backend = make_backend(observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    assert app.new_game(HARD, True)
    app.runtime.state = state
    before = app.snapshot()
    detector, observer = backend.detector, backend.observer
    assert not app.set_aruco_profile("robust_glare")
    assert app.profile_change_error == "No se puede cambiar el perfil durante una partida activa."
    assert backend.detector is detector and backend.observer is observer
    assert app.snapshot() == before
    assert backend.modbus_client.commands == []
    app.close()


def test_profile_construction_failure_is_atomic_and_ui_safe(monkeypatch):
    import ur_tictactoe.desktop.real_backend as module

    backend = make_backend()
    detector, observer = backend.detector, backend.observer
    def fail(*args):
        raise RuntimeError("detector unavailable")
    monkeypatch.setattr(module, "ArucoDetector", fail)
    app = GameApplication(False, real_backend=backend)
    assert not app.set_aruco_profile("robust_glare")
    assert app.profile_change_error == "No se pudo aplicar el perfil de visión."
    assert backend.detector is detector and backend.observer is observer
    assert backend.aruco_profile == "robust"


def test_simulation_profile_is_session_only_without_detector(monkeypatch):
    import ur_tictactoe.desktop.real_backend as module
    def fail(*args):
        raise AssertionError("Simulation must not construct a detector")
    monkeypatch.setattr(module, "ArucoDetector", fail)
    app = GameApplication(True)
    assert app.set_aruco_profile("robust_glare")
    assert app.diagnostic_snapshot().profile == "robust_glare"
    assert app.config.aruco_profile == "robust"
    assert GameApplication(True, config=app.config).diagnostic_snapshot().profile == "robust"
