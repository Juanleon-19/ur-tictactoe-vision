from __future__ import annotations

from dataclasses import dataclass

import pytest

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
        return self.statuses.pop(0)

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
    assert camera.close_calls == modbus.close_calls == 1


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
    assert backend.robot_status == "ERROR"
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
    modbus = FakeModbus((STATUS_READY, STATUS_BUSY, STATUS_DONE))
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


def test_real_modbus_error_stops_runtime() -> None:
    backend = StubBackend(physical(), FakeModbus((STATUS_ERROR,)))
    app = GameApplication(False, real_backend=backend)
    app.update()
    app.new_game(HARD, False)
    app.update()
    assert app.runtime.state == RuntimeState.ERROR
    assert app.snapshot().robot_status == "ERROR"


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
