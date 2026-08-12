from __future__ import annotations

from pathlib import Path

import pytest

import cv2

from ur_tictactoe.config import camera_backend_id, load_vision_config


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


def test_rejects_non_v1_frame_ids_even_with_correct_count(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [4, 5, 6, 7]\n"
        "  cell_ids: [10, 11, 12, 13, 14, 15, 16, 17, 18]",
    )

    with pytest.raises(ValueError, match=r"frame_ids must be exactly \[0, 1, 2, 3\] for V1"):
        load_vision_config(path)


def test_rejects_non_v1_cell_ids_even_with_correct_count(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [0, 1, 2, 3]\n"
        "  cell_ids: [20, 21, 22, 23, 24, 25, 26, 27, 28]",
    )

    with pytest.raises(ValueError, match=r"cell_ids must be exactly \[10, 11, 12"):
        load_vision_config(path)


def test_rejects_reordered_v1_ids(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    _write_config(
        path,
        "  frame_ids: [0, 1, 3, 2]\n"
        "  cell_ids: [10, 11, 12, 13, 14, 15, 16, 17, 18]",
    )

    with pytest.raises(ValueError, match="frame_ids must be exactly"):
        load_vision_config(path)


@pytest.mark.parametrize(
    ("name", "opencv_id"),
    [
        ("AUTO", cv2.CAP_ANY),
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
    ],
)
def test_maps_camera_backend_to_opencv(name: str, opencv_id: int) -> None:
    assert camera_backend_id(name) == opencv_id


def test_rejects_unknown_camera_backend(tmp_path: Path) -> None:
    path = tmp_path / "vision.yaml"
    path.write_text("camera:\n  backend: INVALID\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown camera backend 'INVALID'"):
        load_vision_config(path)
