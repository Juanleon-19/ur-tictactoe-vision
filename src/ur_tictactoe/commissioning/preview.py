"""Operator preview only: render detections without updating board state."""

import cv2

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.aruco import DetectionResult, draw_detections


class VisionPreview:
    title = "Robot Triqui - Commissioning C2"

    def __init__(self, profile):
        self.profile = profile
        self._closed = True

    def __enter__(self):
        cv2.namedWindow(self.title, cv2.WINDOW_NORMAL)
        self._closed = False
        return self

    def is_open(self):
        if self._closed:
            return False
        try:
            visible = cv2.getWindowProperty(self.title, cv2.WND_PROP_VISIBLE)
        except cv2.error:
            # HighGUI can report a destroyed native window by raising instead
            # of returning -1. Latch closure: imshow must never recreate it.
            visible = -1
        if visible < 1:
            self._closed = True
        return not self._closed

    def poll_key(self):
        if not self.is_open():
            return 27
        key = cv2.waitKey(15) & 0xFF
        return key if self.is_open() else 27

    def show(self, frame, detection, fps):
        if not self.is_open():
            return 27
        operational = [(corners, marker) for corners, marker in
                       zip(detection.corners, detection.ids) if marker in CELL_IDS]
        result = DetectionResult(tuple(c for c, _ in operational),
                                 tuple(marker for _, marker in operational))
        display = draw_detections(frame, result)
        visible = sorted(result.id_set)
        missing = sorted(set(CELL_IDS) - result.id_set)
        lines = (
            f"Profile: {self.profile}",
            "Click preview for focus | C = medir | Q/Esc = cancelar",
            f"Visibles {len(visible)}/9: {visible}",
            f"Missing IDs: {missing} | FPS: {fps:.1f}",
        )
        for row, text in enumerate(lines):
            point = (12, 28 + row * 28)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 1, cv2.LINE_AA)
        if not self.is_open():
            return 27
        cv2.imshow(self.title, display)
        return self.poll_key()

    def __exit__(self, exc_type, exc, traceback):
        if self.is_open():
            cv2.destroyWindow(self.title)
        self._closed = True
