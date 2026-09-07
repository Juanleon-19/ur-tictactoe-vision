from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MarkerStatus:
    cell_markers_visible: int
    missing_cell_ids: frozenset[int]


def calculate_marker_status(
    visible_ids: Iterable[int],
    cell_ids: Iterable[int],
) -> MarkerStatus:
    visible = set(visible_ids)
    cells = set(cell_ids)
    missing_cells = cells - visible

    return MarkerStatus(
        cell_markers_visible=len(cells & visible),
        missing_cell_ids=frozenset(missing_cells),
    )
