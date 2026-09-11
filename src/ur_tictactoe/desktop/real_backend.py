"""Small lifecycle boundary for the real camera and robot resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from time import monotonic
from threading import RLock

import numpy as np

from ur_tictactoe.communication import ModbusClient
from ur_tictactoe.communication.dashboard_client import DashboardClient, DashboardSnapshot
from ur_tictactoe.communication.robot_recovery import reset_to_ready
from ur_tictactoe.config import CELL_IDS, CAMERA_BACKENDS, VisionConfig
from ur_tictactoe.desktop.diagnostics import DiagnosticSnapshot, ProfileMeasurements, diagnostic_frame, illumination_status
from ur_tictactoe.vision.aruco import ARUCO_PROFILES, ArucoDetector
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
        modbus_factory: Callable[[], object] | None = None,
        dashboard_enabled: bool = False,
        dashboard_client: object | None = None,
    ) -> None:
        self._dictionary = vision_config.aruco.dictionary
        self._observer_config = vision_config.observer
        self.camera_config = vision_config.camera
        self._camera_factory = camera_factory
        self.camera = camera_factory(self.camera_config)
        self._last_frame_time = None
        self._fps = None
        self._illumination = "NO DISPONIBLE"
        self.detector = detector or ArucoDetector(
            vision_config.aruco.dictionary, aruco_profile
        )
        self.observer = observer or BoardObserver(vision_config.observer)
        self._modbus_factory = modbus_factory or (
            (lambda: modbus_client) if modbus_client is not None else
            (lambda: ModbusClient(robot_host, port=robot_port))
        )
        self.modbus_client = modbus_client or (
            self._modbus_factory() if robot_host or modbus_factory else None
        )
        self.dashboard_enabled = dashboard_enabled
        self._dashboard_client = dashboard_client or (DashboardClient(robot_host) if robot_host else None)
        self.dashboard = DashboardSnapshot()
        self.modbus_status = "NO CONECTADO"
        self.controller_status = "DESCONOCIDO"
        self.robot_error = None
        self._camera_lock = RLock()
        self._robot_lock = RLock()
        self.camera_status = "NO CONECTADA"
        self.robot_status = "NO CONECTADO"
        self.last_error: str | None = None
        self.last_observation: PhysicalBoardState | None = None
        self._camera_open = False
        self._robot_open = False
        self._closed = False
        self._robot_configured = bool(robot_host) or modbus_client is not None or modbus_factory is not None
        self.aruco_profile = aruco_profile
        self._preview = None
        self._visible_ids: tuple[int, ...] = ()
        self.profile_measurements = ProfileMeasurements()

    def set_aruco_profile(self, profile: str) -> None:
        """Replace vision state between UI ticks without touching device resources."""
        if profile not in ARUCO_PROFILES:
            raise ValueError("Invalid ArUco profile")
        detector = ArucoDetector(self._dictionary, profile)
        observer = BoardObserver(self._observer_config)
        self.detector = detector
        self.observer = observer
        self.aruco_profile = profile
        self.profile_measurements.select(profile)
        self.last_observation = None
        self._visible_ids = ()
        self._preview = None
        self._last_frame_time = None
        self._fps = None
        self._illumination = "NO DISPONIBLE"

    def reset_board_observation(self) -> None:
        """Discard temporal evidence without restarting capture or detection."""
        self.observer = BoardObserver(self._observer_config)
        self.last_observation = None
        self._visible_ids = ()
        self._preview = None
        self._last_frame_time = None
        self._fps = None
        self._illumination = "NO DISPONIBLE"

    def apply_camera(self, index: int, backend: str) -> bool:
        if type(index) is not int or index < 0 or backend not in CAMERA_BACKENDS:
            raise ValueError("Configuración de cámara no válida")
        with self._camera_lock:
            config = replace(self.camera_config, index=index, backend=backend)
            return self._reconnect_camera(config)

    def reconnect_camera(self) -> bool:
        """Only camera resources are replaced; robot availability is retained."""
        with self._camera_lock:
            return self._reconnect_camera()

    def _reconnect_camera(self, config=None) -> bool:
        self._camera_open = False
        self.camera_status = "Inicializando cámara..."
        self.profile_measurements = ProfileMeasurements()
        self.reset_board_observation()
        try:
            self.camera.close()
            if config is not None:
                self.camera_config = config
            self.camera = self._camera_factory(self.camera_config)
            self.camera.open()
            self._camera_open = True
            self.camera_status = "CONECTADA"
            if self.last_error and self.last_error.startswith("CAMERA_"):
                self.last_error = None
            return True
        except Exception as exc:
            self.camera_status = "ERROR"
            self.last_error = f"CAMERA_OPEN_ERROR: {exc}"
            try:
                self.camera.close()
            except Exception as close_exc:
                self.last_error += f"; CAMERA_CLOSE_ERROR: {close_exc}"
            return False

    def diagnostic_snapshot(self) -> DiagnosticSnapshot:
        state = self.last_observation
        preview = self._preview
        return DiagnosticSnapshot(
            camera_status=self.camera_status,
            camera_index=self.camera_config.index,
            backend=self.camera_config.backend,
            fps=self._fps,
            illumination=self._illumination,
            profile=self.aruco_profile,
            visible_ids=self._visible_ids,
            resolution=(preview.shape[1], preview.shape[0])
            if preview is not None else None,
            cells=tuple(state.cells[cell] for cell in range(1, 10))
            if state is not None else DiagnosticSnapshot().cells,
            frame=preview,
            profile_samples=self.profile_measurements.snapshot(),
            modbus_status=self.modbus_status,
            controller_status=self.controller_status,
            robot_error=self.robot_error,
            dashboard=self.dashboard,
            camera_open_seconds=getattr(self.camera, "camera_open_seconds", None),
            first_frame_seconds=getattr(self.camera, "first_frame_seconds", None),
            capture_open_seconds=getattr(self.camera, "capture_open_seconds", None),
            configure_seconds=getattr(self.camera, "configure_seconds", None),
            first_frame_read_seconds=getattr(self.camera, "first_frame_read_seconds", None),
            opening_seconds=getattr(self.camera, "opening_seconds", None),
            effective_backend=getattr(self.camera, "effective_backend", None),
        )

    @property
    def is_open(self) -> bool:
        return self._camera_open and self._robot_open

    def open(self) -> bool:
        """Open camera and Modbus independently, retaining clear partial status."""
        with self._camera_lock:
            return self._open()

    def _open(self) -> bool:
        self._closed = False
        self.last_error = None
        if not self._camera_open:
            try:
                self.camera_status = "Inicializando cámara..."
                self.camera.open()
                self._camera_open = True
                self.camera_status = "CONECTADA"
            except Exception as exc:
                self.camera_status = "ERROR"
                self.last_error = f"CAMERA_OPEN_ERROR: {exc}"

        if not self._robot_open:
            self._query_robot(fresh=False)
        return self.is_open

    def refresh_status(self) -> bool:
        """Reuse camera/observer evidence; query STATUS129 through a fresh socket."""
        return self._query_robot(fresh=True)

    def reconnect_robot(self) -> bool:
        """Discard the local connection and perform the same read-only probe."""
        return self._query_robot(fresh=True)

    def record_robot_status(self, status: int | None, error: Exception | None = None) -> None:
        """Present a read already performed by runtime; never query or advance it."""
        if status is not None:
            self.modbus_status = "CONECTADO"
            self.controller_status = {0: "READY", 1: "BUSY", 2: "DONE", 3: "ERROR"}.get(status, "DESCONOCIDO")
            self._robot_open = status == 0
            self.robot_status = {0: "LISTO", 1: "EN MOVIMIENTO"}.get(status, "REQUIERE RECUPERACIÓN")
        elif error is not None:
            self.modbus_status = "ERROR"
            self.controller_status = "DESCONOCIDO"
            self._robot_open = False
            self.robot_status = "ERROR DE CONEXIÓN"

    def _set_robot_error(self, reason: str | None) -> None:
        """Replace only our previous robot diagnostic, retaining camera errors."""
        if self.robot_error and self.last_error:
            self.last_error = self.last_error.replace(self.robot_error, "").strip("; ") or None
        self.robot_error = reason
        if reason:
            self.last_error = "; ".join(filter(None, (self.last_error, reason)))

    def _refresh_dashboard(self, *, force=False) -> None:
        # Optional and advisory: never change Modbus status or game authorization.
        try:
            self.dashboard = (self._dashboard_client.snapshot()
                              if (self.dashboard_enabled or force) and self._dashboard_client else DashboardSnapshot())
        except Exception as exc:
            self.dashboard = DashboardSnapshot(detail=f"Dashboard no disponible: {exc}")

    def recover_robot(self, *, timeout=3.0, clock=monotonic, wait=None) -> bool:
        """Explicit recovery only: fresh connection, at most one COMMAND0, close."""
        with self._robot_lock:
            self._robot_open = False
            if not self._robot_configured:
                self.robot_status = self.modbus_status = "NO CONFIGURADO"
                self._set_robot_error("Robot no configurado. No se escribió COMMAND0.")
                return False
            stage = "cerrar conexión anterior"
            try:
                self.modbus_client.close()
                stage = "crear conexión fresca"
                self.modbus_client = self._modbus_factory()
                try:
                    stage = "conectar TCP"
                    self.modbus_client.connect()
                    stage = "recuperar mediante STATUS129 / COMMAND0 (sin reintentos)"
                    options = {"timeout": timeout, "clock": clock}
                    if wait is not None:
                        options["wait"] = wait
                    result = reset_to_ready(self.modbus_client, **options)
                finally:
                    previous_stage = stage
                    stage = "cerrar conexión de recuperación"
                    self.modbus_client.close()
                    stage = previous_stage
                self.record_robot_status(result.status)
                self._robot_open = result.ready
                if not result.ready and result.status != 1:
                    self.robot_status = "REQUIERE RECUPERACIÓN"
                self._set_robot_error(None if result.ready else result.message)
            except Exception as exc:
                self.record_robot_status(None, exc)
                self._set_robot_error(f"MODBUS_RECOVERY_ERROR: {stage}: {exc}")
            self._refresh_dashboard(force=True)
            return self._robot_open

    def _query_robot(self, *, fresh: bool) -> bool:
        with self._robot_lock:
            # Clear only the previous diagnostic error, never runtime evidence.
            self._set_robot_error(None)
            self._robot_open = False
            self.controller_status = "DESCONOCIDO"
            if not self._robot_configured:
                self.modbus_status = self.robot_status = "NO CONFIGURADO"
                return False
            stage = "descartar conexión local"
            try:
                if fresh:
                    self.modbus_client.close()
                    stage = "crear cliente fresco"
                    self.modbus_client = self._modbus_factory()
                try:
                    stage = "conectar TCP"
                    self.modbus_client.connect()
                    stage = "leer STATUS129"
                    status = self.modbus_client.read_status()
                finally:
                    # A close failure must be identified separately from a read failure.
                    previous_stage = stage
                    stage = "cerrar conexión de consulta"
                    self.modbus_client.close()
                    stage = previous_stage
                self.record_robot_status(status)
                if not self._robot_open:
                    self.robot_error = f"STATUS129: {self.controller_status} ({status}). Revisar PolyScope; sin reset ni reenvío."
            except Exception as exc:
                self.record_robot_status(None, exc)
                self.robot_error = f"MODBUS_CONNECTION_ERROR: {stage}: {exc}"
            if self.robot_error:
                self.last_error = "; ".join(filter(None, (self.last_error, self.robot_error)))
            # Advisory only. This result cannot alter Modbus availability or handshake.
            self._refresh_dashboard()
            return self._robot_open

    def tick(self) -> PhysicalBoardState | None:
        """Capture and process at most one frame, returning the latest state."""
        with self._camera_lock:
            return self._tick()

    def _tick(self) -> PhysicalBoardState | None:
        if not self._camera_open:
            return self.last_observation
        try:
            frame = self.camera.read()
            now = monotonic()
            if self._last_frame_time is not None and now > self._last_frame_time:
                self._fps = 1 / (now - self._last_frame_time)
            self._last_frame_time = now
            detection = self.detector.detect(frame)
            self._illumination = illumination_status(frame) if isinstance(frame, np.ndarray) else "NO DISPONIBLE"
            self.observer.update(detection.id_set)
            self.last_observation = self.observer.state
            self._visible_ids = tuple(sorted(detection.id_set.intersection(CELL_IDS)))
            self.profile_measurements.update(self.aruco_profile, detection.id_set, now)
            self._preview = diagnostic_frame(frame, detection) if isinstance(frame, np.ndarray) else None
            self.camera_status = "CONECTADA"
        except Exception as exc:
            self.profile_measurements = ProfileMeasurements()
            self.reset_board_observation()
            self.camera_status = "ERROR"
            self.last_error = f"CAMERA_CAPTURE_ERROR: {exc}"
        return self.last_observation

    def close(self) -> None:
        """Release both resources; repeated calls are safe."""
        with self._camera_lock, self._robot_lock:
            self._close()

    def _close(self) -> None:
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
        self.modbus_status = "NO CONECTADO"
        self.controller_status = "DESCONOCIDO"
        try:
            close_dashboard = getattr(self._dashboard_client, "close", None)
            if close_dashboard is not None:
                close_dashboard()
        except Exception as exc:
            errors.append(f"DASHBOARD_CLOSE_ERROR: {exc}")
        if errors:
            self.last_error = "; ".join(errors)
