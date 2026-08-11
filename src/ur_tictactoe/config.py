from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30


@dataclass(frozen=True)
class ArucoConfig:
    dictionary: str = "DICT_5X5_50"
    expected_ids: tuple[int, ...] = (0, 1, 2, 3)


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


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{name}' must be a mapping.")
    return value


def load_vision_config(path: Path) -> VisionConfig:
    if not path.exists():
        raise FileNotFoundError(f"Vision configuration not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ValueError("Vision configuration root must be a mapping.")

    camera_raw = _section(raw, "camera")
    aruco_raw = _section(raw, "aruco")
    ui_raw = _section(raw, "ui")

    expected_ids = tuple(int(value) for value in aruco_raw.get("expected_ids", [0, 1, 2, 3]))
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("aruco.expected_ids must not contain duplicate IDs.")

    camera = CameraConfig(
        index=int(camera_raw.get("index", 0)),
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
            expected_ids=expected_ids,
        ),
        ui=UIConfig(
            window_name=str(ui_raw.get("window_name", "UR Tic-Tac-Toe Vision")),
            show_fps=bool(ui_raw.get("show_fps", True)),
            show_marker_centers=bool(ui_raw.get("show_marker_centers", True)),
        ),
    )
