"""Presentation-only view of the existing camera pipeline."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.aruco import DetectionResult, draw_detections
from ur_tictactoe.vision.board_observer import CellState


@dataclass(frozen=True)
class DiagnosticSnapshot:
    camera_status: str = "CÁMARA NO DISPONIBLE"
    profile: str = "robust"
    visible_ids: tuple[int, ...] = ()
    resolution: tuple[int, int] | None = None
    cells: tuple[CellState, ...] = (CellState.UNCERTAIN,) * 9
    frame: np.ndarray | None = field(default=None, repr=False, compare=False)


def diagnostic_frame(frame: np.ndarray, detection: DetectionResult) -> np.ndarray:
    """Annotate operational markers and produce RGB for presentation."""
    pairs = [(corner, marker) for corner, marker in zip(detection.corners, detection.ids)
             if marker in CELL_IDS]
    filtered = DetectionResult(tuple(pair[0] for pair in pairs),
                               tuple(pair[1] for pair in pairs))
    return cv2.cvtColor(draw_detections(frame, filtered), cv2.COLOR_BGR2RGB)
