from __future__ import annotations

import cv2

from ur_tictactoe.config import CameraConfig


class Camera:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        capture = cv2.VideoCapture(self.config.index)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"Could not open camera index {self.config.index}. "
                "Check the configured index and whether another application is using it."
            )

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        self._capture = capture

    def read(self):
        if self._capture is None:
            raise RuntimeError("Camera is not open.")

        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise RuntimeError("Camera frame acquisition failed.")
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
