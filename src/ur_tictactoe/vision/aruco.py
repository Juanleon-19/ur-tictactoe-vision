from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ur_tictactoe.config import CELL_IDS

TEST_BOARD_SIZE = (1920, 1080)
TEST_BOARD_DICTIONARY = "DICT_5X5_50"
ARUCO_PROFILES = ("default", "robust", "robust_glare")


@dataclass(frozen=True)
class DetectionResult:
    corners: tuple[np.ndarray, ...]
    ids: tuple[int, ...]

    @property
    def id_set(self) -> set[int]:
        return set(self.ids)


def build_detector_parameters(profile: str = "default"):
    if profile not in ARUCO_PROFILES:
        raise ValueError(f"Unknown ArUco profile: {profile}")

    parameters = cv2.aruco.DetectorParameters()
    if profile in ("robust", "robust_glare"):
        # Keep the default window range, but sample it more granularly.
        parameters.adaptiveThreshWinSizeStep = 4
        if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
            parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        if hasattr(parameters, "useAruco3Detection"):
            parameters.useAruco3Detection = True
    if profile == "robust_glare":
        # Experimental: extend robust's local threshold windows (3..23 -> 3..43,
        # step 4) for uneven lighting. Keep threshold constant, error correction,
        # border tolerance and polygon approximation at OpenCV defaults.
        # No preprocessing: both profiles receive the original frame unchanged.
        parameters.adaptiveThreshWinSizeMin = 3
        parameters.adaptiveThreshWinSizeMax = 43
        parameters.adaptiveThreshWinSizeStep = 4
    return parameters


class ArucoDetector:
    def __init__(self, dictionary_name: str, profile: str = "default") -> None:
        if not hasattr(cv2.aruco, dictionary_name):
            raise ValueError(f"Unknown ArUco dictionary: {dictionary_name}")

        dictionary_id = getattr(cv2.aruco, dictionary_name)
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        parameters = build_detector_parameters(profile)
        self.profile = profile
        self.parameters = parameters
        self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    def detect(self, frame: np.ndarray) -> DetectionResult:
        corners, ids, _rejected = self._detector.detectMarkers(frame)
        if ids is None:
            return DetectionResult(corners=tuple(), ids=tuple())

        flat_ids = tuple(int(value) for value in ids.flatten())
        return DetectionResult(corners=tuple(corners), ids=flat_ids)


def generate_test_board(output_path: str) -> None:
    width, height = TEST_BOARD_SIZE
    canvas = np.full((height, width), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)

    cell_size = 130
    cell_positions = tuple(
        (700 + column * 245, 330 + row * 210)
        for row in range(3)
        for column in range(3)
    )

    for marker_id, (x, y) in zip(CELL_IDS, cell_positions):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, cell_size)
        canvas[y : y + cell_size, x : x + cell_size] = marker

    if not cv2.imwrite(output_path, canvas):
        raise RuntimeError(f"Could not write ArUco test board: {output_path}")


def draw_detections(
    frame: np.ndarray,
    result: DetectionResult,
    show_centers: bool = True,
) -> np.ndarray:
    output = frame.copy()
    if not result.ids:
        return output

    ids_array = np.asarray(result.ids, dtype=np.int32).reshape(-1, 1)
    cv2.aruco.drawDetectedMarkers(output, list(result.corners), ids_array)

    if show_centers:
        for marker_id, marker_corners in zip(result.ids, result.corners):
            points = marker_corners.reshape(4, 2)
            center = points.mean(axis=0).astype(int)
            cv2.circle(output, tuple(center), 4, (255, 255, 255), -1)
            cv2.putText(
                output,
                f"ID {marker_id}",
                (int(center[0]) + 8, int(center[1]) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    return output
