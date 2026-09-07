from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
import cv2

CELL_IDS = (10, 11, 12, 13, 14, 15, 16, 17, 18)
CAMERA_BACKENDS = {
    "AUTO": cv2.CAP_ANY,
    "DSHOW": cv2.CAP_DSHOW,
    "MSMF": cv2.CAP_MSMF,
}


def camera_backend_id(name: str) -> int:
    try:
        return CAMERA_BACKENDS[name]
    except KeyError as exc:
        supported = ", ".join(CAMERA_BACKENDS)
        raise ValueError(
            f"Unknown camera backend '{name}'. Supported values: {supported}."
        ) from exc


@dataclass(frozen=True)
class CameraConfig:
    index: int = 0
    backend: str = "AUTO"
    width: int = 1280
    height: int = 720
    fps: int = 30


@dataclass(frozen=True)
class ArucoConfig:
    dictionary: str = "DICT_5X5_50"
    cell_ids: tuple[int, ...] = CELL_IDS

    @property
    def all_ids(self) -> tuple[int, ...]:
        return self.cell_ids


@dataclass(frozen=True)
class UIConfig:
    window_name: str = "UR Tic-Tac-Toe Vision"
    show_fps: bool = True
    show_marker_centers: bool = True


@dataclass(frozen=True)
class VisionConfig:
    camera: CameraConfig
    aruco: ArucoConfig
    ui: UIConfig
    observer: "ObserverConfig"


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{name}' must be a mapping.")
    return value


def _parse_ids(raw: dict[str, Any], key: str, default: list[int]) -> tuple[int, ...]:
    ids = tuple(int(value) for value in raw.get(key, default))
    if len(ids) != len(set(ids)):
        raise ValueError(f"aruco.{key} must not contain duplicate IDs.")
    return ids


def load_vision_config(path: Path) -> VisionConfig:
    from ur_tictactoe.vision.board_observer import ObserverConfig
    if not path.exists():
        raise FileNotFoundError(f"Vision configuration not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ValueError("Vision configuration root must be a mapping.")

    camera_raw = _section(raw, "camera")
    aruco_raw = _section(raw, "aruco")
    ui_raw = _section(raw, "ui")
    observer_raw = _section(raw, "observer")

    cell_ids = _parse_ids(
        aruco_raw,
        "cell_ids",
        list(CELL_IDS),
    )

    if cell_ids != CELL_IDS:
        raise ValueError(f"aruco.cell_ids must be exactly {list(CELL_IDS)} for V1.")

    backend = str(camera_raw.get("backend", "AUTO")).upper()
    camera_backend_id(backend)
    camera = CameraConfig(
        index=int(camera_raw.get("index", 0)),
        backend=backend,
        width=int(camera_raw.get("width", 1280)),
        height=int(camera_raw.get("height", 720)),
        fps=int(camera_raw.get("fps", 30)),
    )
    if camera.width <= 0 or camera.height <= 0 or camera.fps <= 0:
        raise ValueError("Camera width, height and fps must be positive values.")

    return VisionConfig(
        camera=camera,
        aruco=ArucoConfig(
            dictionary=str(aruco_raw.get("dictionary", "DICT_5X5_50")),
            cell_ids=cell_ids,
        ),
        ui=UIConfig(
            window_name=str(ui_raw.get("window_name", "UR Tic-Tac-Toe Vision")),
            show_fps=bool(ui_raw.get("show_fps", True)),
            show_marker_centers=bool(ui_raw.get("show_marker_centers", True)),
        ),
        observer=ObserverConfig(
            window_seconds=float(observer_raw.get("window_seconds", 1.5)),
            evaluation_period_seconds=float(
                observer_raw.get("evaluation_period_seconds", 0.25)
            ),
            state_change_seconds=float(observer_raw.get("state_change_seconds", 0.5)),
            free_ratio=float(observer_raw.get("free_ratio", 0.70)),
            occupied_ratio=float(observer_raw.get("occupied_ratio", 0.20)),
            min_valid_samples=int(observer_raw.get("min_valid_samples", 3)),
        ),
    )
