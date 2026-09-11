"""Presentation-only view of the existing camera pipeline."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.communication.dashboard_client import DashboardSnapshot
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
    profile_samples: tuple = ()
    modbus_status: str = "NO CONECTADO"
    controller_status: str = "DESCONOCIDO"
    robot_error: str | None = None
    game_history: tuple[str, ...] = ()
    dashboard: DashboardSnapshot = field(default_factory=DashboardSnapshot)
    camera_open_seconds: float | None = None
    first_frame_seconds: float | None = None
    capture_open_seconds: float | None = None
    configure_seconds: float | None = None
    first_frame_read_seconds: float | None = None
    opening_seconds: float | None = None
    effective_backend: str | None = None


class ProfileMeasurements:
    """Presentation-only counts from existing detections, one interval per profile."""

    def __init__(self):
        self.samples = {}
        self.active = None

    def select(self, profile):
        self.active = profile
        self.samples.pop(profile, None)

    def update(self, profile, visible, timestamp):
        if profile != self.active:
            self.select(profile)
        sample = self.samples.setdefault(profile, [0, timestamp, timestamp, [0] * 9])
        sample[0] += 1
        sample[2] = timestamp
        for index, marker in enumerate(CELL_IDS):
            sample[3][index] += marker in visible

    def snapshot(self):
        return tuple((profile, count, end - start,
                      (count - 1) / (end - start) if end > start else None,
                      tuple(100 * hits / count for hits in counts))
                     for profile, (count, start, end, counts) in self.samples.items())


def profile_comparison(samples):
    lines = ["Compare con el mismo tablero vacío, encuadre e iluminación.",
             "Observe al menos 10 s por perfil. Cambiar de perfil reinicia su muestra.",
             "Visibilidad = % de frames con cada ID; FPS incluye el ritmo de la GUI.",
             "Reflejos es experimental: estos datos no demuestran superioridad física.", ""]
    measured = {sample[0]: sample for sample in samples}
    for profile, title in (("robust", "Robusto (predeterminado)"),
                           ("robust_glare", "Reflejos (experimental)"), ("default", "Estándar")):
        sample = measured.get(profile)
        if sample is None:
            lines.append(f"{title}: sin muestra")
            continue
        _, count, elapsed, fps, visibility = sample
        rate = f"{fps:.1f}" if fps is not None else "—"
        lines.append(f"{title}: {count} frames · {elapsed:.1f} s · {rate} FPS")
        lines.append("   ".join(f"ID{marker}: {percent:.0f}%"
                                for marker, percent in zip(CELL_IDS, visibility)))
    return "\n\n".join(lines)


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
