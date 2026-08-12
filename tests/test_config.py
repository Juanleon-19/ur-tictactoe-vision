from __future__ import annotations

from pathlib import Path

import pytest

from ur_tictactoe.config import load_vision_config


def _write_config(path: Path, aruco_block: str) -> None:
    path.write_text(
        f"""
camera:
  index: 0
  width: 1280
  height: 720
  fps: 30

aruco:
  dictionary: DICT_5X5_50
{aruco_block}

ui:
  window_name: Test
  show_fps: true
  show_marker_centers: true
""".lstrip(),
        encoding="utf-8",
    )


def test_loads_frame_and_cell_marker_roles(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [0, 1, 2, 3]\n"
        "  cell_ids: [10, 11, 12, 13, 14, 15, 16, 17, 18]",
    )

    config = load_vision_config(path)

    assert config.aruco.frame_ids == (0, 1, 2, 3)
    assert config.aruco.cell_ids == (10, 11, 12, 13, 14, 15, 16, 17, 18)
    assert len(config.aruco.all_ids) == 13


def test_rejects_overlapping_frame_and_cell_ids(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [0, 1, 2, 3]\n"
        "  cell_ids: [3, 11, 12, 13, 14, 15, 16, 17, 18]",
    )

    with pytest.raises(ValueError, match="must not overlap"):
        load_vision_config(path)


def test_requires_exactly_nine_cell_markers(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [0, 1, 2, 3]\n"
        "  cell_ids: [10, 11, 12]",
    )

    with pytest.raises(ValueError, match="exactly nine"):
        load_vision_config(path)
