from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic

import cv2

from ur_tictactoe.config import CameraConfig, camera_backend_id


@dataclass(frozen=True)
class CameraSettings:
    width: int
    height: int
    fps: float


class Camera:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._capture: cv2.VideoCapture | None = None
        self._lock = RLock()
        self.camera_open_seconds = None
        self.capture_open_seconds = None
        self.configure_seconds = None
        self.first_frame_seconds = None
        self.first_frame_read_seconds = None
        self.effective_backend = None
        self._open_started = None
        self._open_finished = None

    @property
    def opening_seconds(self):
        if self._open_started is not None and self._open_finished is None:
            return monotonic() - self._open_started
        return None

    def open(self) -> None:
        # Serialize open/read/release. A second open waits and reuses the capture.
        with self._lock:
            if self._capture is not None:
                return
            self._open_started = monotonic()
            self._open_finished = None
            self.camera_open_seconds = self.capture_open_seconds = self.configure_seconds = None
            self.first_frame_seconds = self.first_frame_read_seconds = None
            self.effective_backend = None
            capture = None
            try:
                capture = cv2.VideoCapture(
                    self.config.index, camera_backend_id(self.config.backend)
                )
                self.capture_open_seconds = monotonic() - self._open_started
                if not capture.isOpened():
                    raise RuntimeError(
                        f"Could not open camera index {self.config.index}. "
                        "Check the configured index and whether another application is using it."
                    )
                configured = monotonic()
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                capture.set(cv2.CAP_PROP_FPS, self.config.fps)
                self.configure_seconds = monotonic() - configured
                self.effective_backend = capture.getBackendName()
                self._capture = capture
            except Exception:
                if capture is not None:
                    capture.release()
                raise
            finally:
                self._open_finished = monotonic()
                self.camera_open_seconds = self._open_finished - self._open_started

    @property
    def effective_settings(self) -> CameraSettings:
        with self._lock:
            return self._effective_settings()

    def _effective_settings(self) -> CameraSettings:
        if self._capture is None:
            raise RuntimeError("Camera is not open.")
        return CameraSettings(
            width=round(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=round(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=self._capture.get(cv2.CAP_PROP_FPS),
        )

    def read(self):
        with self._lock:
            if self._capture is None:
                raise RuntimeError("Camera is not open.")
            started = monotonic()
            ok, frame = self._capture.read()
            if not ok or frame is None:
                raise RuntimeError("Camera frame acquisition failed.")
            if self.first_frame_seconds is None:
                now = monotonic()
                self.first_frame_seconds = now - self._open_finished
                self.first_frame_read_seconds = now - started
            return frame

    def close(self) -> None:
        with self._lock:
            if self._capture is not None:
                capture, self._capture = self._capture, None
                capture.release()

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
