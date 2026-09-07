from __future__ import annotations

import pytest

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.marker_status import calculate_marker_status


@pytest.mark.parametrize(
    ("visible_ids", "visible_cells", "missing_cells"),
    [
        (CELL_IDS, 9, frozenset()),
        (CELL_IDS[:6], 6, frozenset({16, 17, 18})),
        (CELL_IDS + (49,), 9, frozenset()),
        ((), 0, frozenset(CELL_IDS)),
    ],
)
def test_calculates_cell_visibility(visible_ids, visible_cells, missing_cells) -> None:
    status = calculate_marker_status(visible_ids, CELL_IDS)
    assert status.cell_markers_visible == visible_cells
    assert status.missing_cell_ids == missing_cells
