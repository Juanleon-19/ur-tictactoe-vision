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
    camera_index: int = 0
    backend: str = "AUTO"
    fps: float | None = None
    illumination: str = "NO DISPONIBLE"
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


def illumination_status(frame: np.ndarray) -> str:
    """Advisory only: sample luminance, never write into the productive frame."""
    gray = cv2.cvtColor(frame[::8, ::8], cv2.COLOR_BGR2GRAY)
    return ("POSIBLE REFLEJO / SOBREEXPOSICIÓN" if np.mean(gray >= 250) >= 0.05
            else "CORRECTA")


def diagnostic_text(snapshot: DiagnosticSnapshot, board_status: str, error: str | None = None) -> str:
    resolution = "×".join(map(str, snapshot.resolution)) if snapshot.resolution else "—"
    fps = f"{snapshot.fps:.1f}" if snapshot.fps is not None else "—"
    missing = sorted(set(CELL_IDS).difference(snapshot.visible_ids))
    text = (f"Cámara: {snapshot.camera_index} · {snapshot.backend} · {snapshot.camera_status}"
            f" | Resolución: {resolution} | FPS: {fps} (captura GUI)\n"
            f"IDs visibles ({len(snapshot.visible_ids)}/9): {', '.join(map(str, snapshot.visible_ids)) or '—'}\n"
            f"IDs faltantes: {', '.join(map(str, missing)) or 'ninguno'} | Tablero: {board_status}\n"
            f"ILUMINACIÓN: {snapshot.illumination}")
    return text + (f"\nDetalle: {error}" if error else "")
