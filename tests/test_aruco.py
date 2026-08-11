from __future__ import annotations

import cv2
import numpy as np

from ur_tictactoe.vision.aruco import ArucoDetector


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
