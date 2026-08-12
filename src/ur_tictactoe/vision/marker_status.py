from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MarkerStatus:
    frame_ready: bool
    empty_board_ready: bool
    cell_markers_visible: int
    missing_cell_ids: frozenset[int]


def calculate_marker_status(
    visible_ids: Iterable[int],
    frame_ids: Iterable[int],
    cell_ids: Iterable[int],
) -> MarkerStatus:
    visible = set(visible_ids)
    frame = set(frame_ids)
    cells = set(cell_ids)
    missing_cells = cells - visible
    frame_ready = frame.issubset(visible)

    return MarkerStatus(
        frame_ready=frame_ready,
        empty_board_ready=frame_ready and not missing_cells,
        cell_markers_visible=len(cells & visible),
        missing_cell_ids=frozenset(missing_cells),
    )
