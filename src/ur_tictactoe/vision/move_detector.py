"""Detect a human move from stable disappearance of a cell marker."""

from __future__ import annotations

from collections.abc import Iterable

from ur_tictactoe.config import CELL_IDS


def cell_id_to_cell(marker_id: int) -> int:
    """Convert a V1 cell marker ID to its public board cell number."""
    try:
        return CELL_IDS.index(marker_id) + 1
    except ValueError as exc:
        raise ValueError(f"Unknown cell marker ID: {marker_id}") from exc


def cell_to_marker_id(cell: int) -> int:
    """Convert a public board cell number to its V1 marker ID."""
    if isinstance(cell, bool) or not isinstance(cell, int) or not 1 <= cell <= 9:
        raise ValueError(f"Invalid occupied cell: {cell}")
    return CELL_IDS[cell - 1]


class HumanMoveDetector:
    """Confirm one newly missing marker after consecutive stable observations."""

    def __init__(self, stable_frames: int = 5) -> None:
        if (
            isinstance(stable_frames, bool)
            or not isinstance(stable_frames, int)
            or stable_frames <= 0
        ):
            raise ValueError("stable_frames must be a positive integer")
        self.stable_frames = stable_frames
        self._candidate_id: int | None = None
        self._candidate_frames = 0
        self._pending_cells: set[int] = set()

    def update(
        self,
        visible_cell_ids: Iterable[int],
        frame_ready: bool,
        occupied_cells: Iterable[int],
    ) -> int | None:
        visible = set(visible_cell_ids)
        unknown_ids = visible - set(CELL_IDS)
        if unknown_ids:
            raise ValueError(f"Unknown cell marker IDs: {sorted(unknown_ids)}")

        occupied = set(occupied_cells)
        for cell in occupied:
            cell_to_marker_id(cell)

        self._pending_cells.difference_update(occupied)
        if not frame_ready:
            self._reset_candidate()
            return None

        expected_cells = occupied | self._pending_cells
        expected_missing = {cell_to_marker_id(cell) for cell in expected_cells}
        observed_missing = set(CELL_IDS) - visible
        new_missing = observed_missing - expected_missing

        if len(new_missing) != 1:
            self._reset_candidate()
            return None

        marker_id = next(iter(new_missing))
        if marker_id != self._candidate_id:
            self._candidate_id = marker_id
            self._candidate_frames = 1
        else:
            self._candidate_frames += 1

        if self._candidate_frames < self.stable_frames:
            return None

        cell = cell_id_to_cell(marker_id)
        self._pending_cells.add(cell)
        self._reset_candidate()
        return cell

    def _reset_candidate(self) -> None:
        self._candidate_id = None
        self._candidate_frames = 0
