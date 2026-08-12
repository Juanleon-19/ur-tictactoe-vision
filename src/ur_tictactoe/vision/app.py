from __future__ import annotations

import time

import cv2

from ur_tictactoe.config import VisionConfig
from ur_tictactoe.vision.aruco import ArucoDetector, draw_detections
from ur_tictactoe.vision.camera import Camera
from ur_tictactoe.vision.marker_status import calculate_marker_status


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
    previous_time = time.perf_counter()
    fps = 0.0

    try:
        with Camera(config.camera) as camera:
            effective = camera.effective_settings
            print(
                f"Requested camera: {config.camera.width}x{config.camera.height} "
                f"@ {config.camera.fps} FPS"
            )
            print(
                f"Effective camera: {effective.width}x{effective.height} "
                f"@ {effective.fps:g} FPS"
            )
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

                visible_ids = result.id_set
                status = calculate_marker_status(
                    visible_ids, config.aruco.frame_ids, config.aruco.cell_ids
                )

                _draw_status(
                    display,
                    "FRAME READY" if status.frame_ready else "FRAME NOT READY",
                    30,
                )
                _draw_status(
                    display,
                    f"Cell markers visible: {status.cell_markers_visible}/{len(config.aruco.cell_ids)}",
                    60,
                )
                _draw_status(
                    display,
                    "EMPTY BOARD READY" if status.empty_board_ready else "EMPTY BOARD NOT READY",
                    90,
                )

                detected_text = "Detected IDs: " + (
                    ", ".join(str(marker_id) for marker_id in sorted(visible_ids))
                    if result.ids
                    else "none"
                )
                _draw_status(display, detected_text, 120)

                if status.missing_cell_ids:
                    missing_text = "Missing cell IDs: " + ", ".join(
                        str(marker_id) for marker_id in sorted(status.missing_cell_ids)
                    )
                    _draw_status(display, missing_text, 150)

                if config.ui.show_fps:
                    _draw_status(display, f"FPS: {fps:.1f}", 180)

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
