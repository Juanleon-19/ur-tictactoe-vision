"""Local camera discovery without retaining captures or changing configuration."""

import cv2

from ur_tictactoe.config import camera_backend_id


def detect_local_cameras(backend: str, known_open: int | None = None) -> list[int]:
    backend_id = camera_backend_id(backend)
    available = []
    for index in range(6):
        if index == known_open:
            available.append(index)
            continue
        capture = cv2.VideoCapture()
        try:
            capture.open(index, backend_id)
            if capture.isOpened():
                available.append(index)
        except cv2.error:
            continue
        finally:
            capture.release()
    return available
