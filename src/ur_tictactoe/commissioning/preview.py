"""Operator preview only: render detections without updating board state."""

import cv2

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.aruco import DetectionResult, draw_detections


class VisionPreview:
    title = "Robot Triqui - Commissioning C2"

    def __enter__(self):
        cv2.namedWindow(self.title, cv2.WINDOW_NORMAL)
        return self

    def show(self, frame, detection, fps):
        operational = [(corners, marker) for corners, marker in
                       zip(detection.corners, detection.ids) if marker in CELL_IDS]
        result = DetectionResult(tuple(c for c, _ in operational),
                                 tuple(marker for _, marker in operational))
        display = draw_detections(frame, result)
        visible = sorted(result.id_set)
        missing = sorted(set(CELL_IDS) - result.id_set)
        lines = (
            "Posicione camara y tablero. C: confirmar y comenzar medicion. Q/Esc: cancelar.",
            f"Visibles {len(visible)}/9: {visible}",
            f"Missing IDs: {missing} | FPS: {fps:.1f}",
        )
        for row, text in enumerate(lines):
            point = (12, 28 + row * 28)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(self.title, display)
        key = cv2.waitKey(1) & 0xFF
        if cv2.getWindowProperty(self.title, cv2.WND_PROP_VISIBLE) < 1:
            return 27
        return key

    def __exit__(self, exc_type, exc, traceback):
        cv2.destroyWindow(self.title)
