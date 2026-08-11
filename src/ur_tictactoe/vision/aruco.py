from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectionResult:
    corners: tuple[np.ndarray, ...]
    ids: tuple[int, ...]

    @property
    def id_set(self) -> set[int]:
        return set(self.ids)


class ArucoDetector:
    def __init__(self, dictionary_name: str) -> None:
        if not hasattr(cv2.aruco, dictionary_name):
            raise ValueError(f"Unknown ArUco dictionary: {dictionary_name}")

        dictionary_id = getattr(cv2.aruco, dictionary_name)
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        parameters = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    def detect(self, frame: np.ndarray) -> DetectionResult:
        corners, ids, _rejected = self._detector.detectMarkers(frame)
        if ids is None:
            return DetectionResult(corners=tuple(), ids=tuple())

        flat_ids = tuple(int(value) for value in ids.flatten())
        return DetectionResult(corners=tuple(corners), ids=flat_ids)


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
