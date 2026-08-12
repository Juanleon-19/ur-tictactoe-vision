from __future__ import annotations

import cv2
import numpy as np

from ur_tictactoe.vision.aruco import ArucoDetector

APPROVED_IDS = {0, 1, 2, 3, 10, 11, 12, 13, 14, 15, 16, 17, 18}


def test_detects_generated_marker() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 0, 200)

    canvas = np.full((300, 300), 255, dtype=np.uint8)
    canvas[50:250, 50:250] = marker
    frame = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

    detector = ArucoDetector("DICT_5X5_50")
    result = detector.detect(frame)

    assert result.ids == (0,)
    assert len(result.corners) == 1


def test_returns_empty_result_when_no_marker_exists() -> None:
    frame = np.full((300, 300, 3), 255, dtype=np.uint8)

    detector = ArucoDetector("DICT_5X5_50")
    result = detector.detect(frame)

    assert result.ids == ()
    assert result.corners == ()


def test_detects_all_thirteen_approved_markers_in_synthetic_image() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    marker_size = 100
    margin = 25
    canvas = np.full((4 * 150 + margin, 4 * 150 + margin), 255, dtype=np.uint8)

    for index, marker_id in enumerate(sorted(APPROVED_IDS)):
        row, column = divmod(index, 4)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
        y = margin + row * 150
        x = margin + column * 150
        canvas[y : y + marker_size, x : x + marker_size] = marker

    result = ArucoDetector("DICT_5X5_50").detect(
        cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    )

    assert result.id_set == APPROVED_IDS
    assert len(result.ids) == 13
