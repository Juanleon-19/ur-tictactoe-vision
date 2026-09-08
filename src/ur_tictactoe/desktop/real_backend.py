"""Small lifecycle boundary for the real camera and robot resources."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ur_tictactoe.communication import ModbusClient
from ur_tictactoe.config import CELL_IDS, VisionConfig
from ur_tictactoe.desktop.diagnostics import DiagnosticSnapshot, diagnostic_frame
from ur_tictactoe.vision.aruco import ArucoDetector
from ur_tictactoe.vision.board_observer import BoardObserver, PhysicalBoardState
from ur_tictactoe.vision.camera import Camera


class RealGameBackend:
    """Capture one observation per tick and own real resource cleanup."""

    def __init__(
        self,
        vision_config: VisionConfig,
        robot_host: str,
        robot_port: int = 502,
        aruco_profile: str = "robust",
        camera_factory: Callable[[object], object] = Camera,
        detector: object | None = None,
        observer: object | None = None,
        modbus_client: object | None = None,
    ) -> None:
        self.camera = camera_factory(vision_config.camera)
        self.detector = detector or ArucoDetector(
            vision_config.aruco.dictionary, aruco_profile
        )
        self.observer = observer or BoardObserver(vision_config.observer)
        self.modbus_client = modbus_client or (
            ModbusClient(robot_host, port=robot_port) if robot_host else None
        )
        self.camera_status = "NO CONECTADA"
        self.robot_status = "NO CONECTADO"
        self.last_error: str | None = None
        self.last_observation: PhysicalBoardState | None = None
        self._camera_open = False
        self._robot_open = False
        self._closed = False
        self._robot_configured = bool(robot_host) or modbus_client is not None
        self.aruco_profile = aruco_profile
        self._preview = None
        self._visible_ids: tuple[int, ...] = ()

    def diagnostic_snapshot(self) -> DiagnosticSnapshot:
        state = self.last_observation
        return DiagnosticSnapshot(
            camera_status=self.camera_status,
            profile=self.aruco_profile,
            visible_ids=self._visible_ids,
            resolution=(self._preview.shape[1], self._preview.shape[0])
            if self._preview is not None else None,
            cells=tuple(state.cells[cell] for cell in range(1, 10))
            if state is not None else DiagnosticSnapshot().cells,
            frame=self._preview,
        )

    @property
    def is_open(self) -> bool:
        return self._camera_open and self._robot_open

    def open(self) -> bool:
        """Open camera and Modbus independently, retaining clear partial status."""
        self._closed = False
        self.last_error = None
        if not self._camera_open:
            try:
                self.camera.open()
                self._camera_open = True
                self.camera_status = "CONECTADA"
            except Exception as exc:
                self.camera_status = "ERROR"
                self.last_error = f"CAMERA_OPEN_ERROR: {exc}"

        if not self._robot_configured:
            self.robot_status = "NO CONFIGURADO"
        elif not self._robot_open:
            try:
                self.modbus_client.connect()
                self._robot_open = True
                self.robot_status = "LISTO"
            except Exception as exc:
                self.robot_status = "ERROR"
                reason = f"MODBUS_CONNECTION_ERROR: {exc}"
                self.last_error = (
                    f"{self.last_error}; {reason}" if self.last_error else reason
                )
        return self.is_open

    def tick(self) -> PhysicalBoardState | None:
        """Capture and process at most one frame, returning the latest state."""
        if not self._camera_open:
            return self.last_observation
        try:
            frame = self.camera.read()
            detection = self.detector.detect(frame)
            self.observer.update(detection.id_set)
            self.last_observation = self.observer.state
            self._visible_ids = tuple(sorted(detection.id_set.intersection(CELL_IDS)))
            self._preview = diagnostic_frame(frame, detection) if isinstance(frame, np.ndarray) else None
            self.camera_status = "CONECTADA"
        except Exception as exc:
            self._preview = None
            self._visible_ids = ()
            self.camera_status = "ERROR"
            self.last_error = f"CAMERA_CAPTURE_ERROR: {exc}"
        return self.last_observation

    def close(self) -> None:
        """Release both resources; repeated calls are safe."""
        if self._closed:
            return
        self._closed = True
        self._preview = None
        self._visible_ids = ()
        errors: list[str] = []
        try:
            self.camera.close()
        except Exception as exc:
            errors.append(f"CAMERA_CLOSE_ERROR: {exc}")
        self._camera_open = False
        self.camera_status = "NO CONECTADA"
        try:
            if self.modbus_client is not None:
                self.modbus_client.close()
        except Exception as exc:
            errors.append(f"MODBUS_CLOSE_ERROR: {exc}")
        self._robot_open = False
        self.robot_status = "NO CONECTADO"
        if errors:
            self.last_error = "; ".join(errors)
