"""Resolve optional desktop assets in development and frozen applications."""

from __future__ import annotations

from pathlib import Path
import sys


def resource_path(relative_path: str, base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        base = base_dir
    elif getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[3]
    return base / relative_path


def optional_asset(relative_path: str, base_dir: Path | None = None) -> Path | None:
    path = resource_path(relative_path, base_dir)
    return path if path.is_file() else None
