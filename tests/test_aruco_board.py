from __future__ import annotations

from pathlib import Path

import cv2

from ur_tictactoe.config import CELL_IDS, FRAME_IDS
from ur_tictactoe.vision.aruco import ArucoDetector, generate_test_board


def test_generated_board_contains_all_v1_markers(tmp_path: Path) -> None:
    output_path = tmp_path / "aruco_test_board.png"

    generate_test_board(str(output_path))

    assert output_path.exists()
    image = cv2.imread(str(output_path))
    assert image is not None
    result = ArucoDetector("DICT_5X5_50").detect(image)
    assert result.id_set == set(FRAME_IDS + CELL_IDS)
    assert len(result.ids) == 13
