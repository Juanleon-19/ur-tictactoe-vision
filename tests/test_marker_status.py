from __future__ import annotations

import pytest

from ur_tictactoe.config import CELL_IDS, FRAME_IDS
from ur_tictactoe.vision.marker_status import calculate_marker_status


@pytest.mark.parametrize(
    ("visible_ids", "frame_ready", "empty_ready", "visible_cells", "missing_cells"),
    [
        (FRAME_IDS + CELL_IDS, True, True, 9, frozenset()),
        (FRAME_IDS + CELL_IDS[:6], True, False, 6, frozenset({16, 17, 18})),
        (FRAME_IDS[:3] + CELL_IDS, False, False, 9, frozenset()),
        ((), False, False, 0, frozenset(CELL_IDS)),
    ],
)
def test_calculates_marker_visibility_status(
    visible_ids,
    frame_ready,
    empty_ready,
    visible_cells,
    missing_cells,
) -> None:
    status = calculate_marker_status(visible_ids, FRAME_IDS, CELL_IDS)

    assert status.frame_ready is frame_ready
    assert status.empty_board_ready is empty_ready
    assert status.cell_markers_visible == visible_cells
    assert status.missing_cell_ids == missing_cells
