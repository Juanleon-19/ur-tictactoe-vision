"""External desktop settings, resolved independently of the working directory."""

from dataclasses import dataclass, field
from pathlib import Path
import sys

import yaml

from ur_tictactoe.desktop.assets import resource_path
from ur_tictactoe.vision.aruco import ARUCO_PROFILES


def application_directory() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else resource_path("")


def default_vision_path() -> Path:
    external = application_directory() / "config/vision.yaml"
    return external if external.is_file() else resource_path("config/vision.example.yaml")


@dataclass(frozen=True)
class AppConfig:
    robot_host: str = ""
    robot_port: int = 502
    update_interval_ms: int = 100
    vision_config_path: Path = field(default_factory=default_vision_path)
    aruco_profile: str = "robust"


def load_app_config(path: Path | None = None) -> AppConfig:
    explicit = path is not None
    path = path or application_directory() / "config/app.yaml"
    if not path.is_file() and not explicit:
        return AppConfig()
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Application configuration must be a mapping")
    robot, ui = raw.get("robot", {}), raw.get("ui", {})
    if not isinstance(robot, dict) or not isinstance(ui, dict):
        raise ValueError("robot and ui must be mappings")
    host = robot.get("host") or ""
    port = int(robot.get("port", 502))
    interval = int(ui.get("update_interval_ms", 100))
    profile = raw.get("aruco_profile", "robust")
    if not isinstance(host, str) or not 1 <= port <= 65535 or interval <= 0:
        raise ValueError("Invalid robot host, port or update interval")
    if profile not in ARUCO_PROFILES:
        raise ValueError("Unknown ArUco profile")
    vision = Path(raw["vision_config"]) if raw.get("vision_config") else None
    if vision is not None and not vision.is_absolute():
        vision = path.resolve().parent / vision
    return AppConfig(host, port, interval, vision or default_vision_path(), profile)
