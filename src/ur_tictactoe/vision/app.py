from __future__ import annotations

import time

import cv2

from ur_tictactoe.config import VisionConfig
from ur_tictactoe.vision.aruco import ArucoDetector, draw_detections
from ur_tictactoe.vision.camera import Camera


def _draw_status(frame, text: str, y: int) -> None:
    cv2.putText(
        frame,
        text,
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def run_vision(config: VisionConfig) -> int:
    detector = ArucoDetector(config.aruco.dictionary)
    expected_ids = set(config.aruco.expected_ids)

    previous_time = time.perf_counter()
    fps = 0.0

    try:
        with Camera(config.camera) as camera:
            print("[INFO] Vision running. Press q or Esc to close.")

            while True:
                frame = camera.read()
                result = detector.detect(frame)
                display = draw_detections(
                    frame,
                    result,
                    show_centers=config.ui.show_marker_centers,
                )

                now = time.perf_counter()
                delta = now - previous_time
                previous_time = now
                if delta > 0:
                    instantaneous_fps = 1.0 / delta
                    fps = instantaneous_fps if fps == 0 else (0.9 * fps + 0.1 * instantaneous_fps)

                detected_expected = expected_ids.issubset(result.id_set)
                board_text = "BOARD DETECTED" if detected_expected else "BOARD NOT DETECTED"
                _draw_status(display, board_text, 30)

                detected_text = "Detected IDs: " + (
                    ", ".join(str(marker_id) for marker_id in sorted(result.id_set))
                    if result.ids
                    else "none"
                )
                _draw_status(display, detected_text, 60)

                if config.ui.show_fps:
                    _draw_status(display, f"FPS: {fps:.1f}", 90)

                cv2.imshow(config.ui.window_name, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break

    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1
    finally:
        cv2.destroyAllWindows()

    return 0
