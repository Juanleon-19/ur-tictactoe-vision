"""Time-based physical board observation from ArUco visibility."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import time
from collections.abc import Iterable, Mapping

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.move_detector import cell_id_to_cell


class CellState(str, Enum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class ObserverConfig:
    window_seconds: float = 1.5
    evaluation_period_seconds: float = 0.25
    state_change_seconds: float = 0.5
    free_ratio: float = 0.70
    occupied_ratio: float = 0.20
    min_valid_samples: int = 3

    def __post_init__(self) -> None:
        if self.window_seconds <= 0 or self.evaluation_period_seconds <= 0:
            raise ValueError("Observer window and evaluation period must be positive")
        if self.state_change_seconds < 0:
            raise ValueError("Observer state change time must not be negative")
        if not 0 <= self.occupied_ratio < self.free_ratio <= 1:
            raise ValueError("Observer ratios must satisfy 0 <= occupied < free <= 1")
        if self.min_valid_samples <= 0:
            raise ValueError("Observer min_valid_samples must be positive")


@dataclass(frozen=True)
class PhysicalBoardState:
    cells: Mapping[int, CellState]
    visibility_ratio: Mapping[int, float]
    ready: bool
    total_samples: int
    detection_ratio: Mapping[int, float]

    @property
    def free_cells(self) -> frozenset[int]:
        return frozenset(cell for cell, state in self.cells.items() if state == CellState.FREE)

    @property
    def occupied_cells(self) -> frozenset[int]:
        return frozenset(cell for cell, state in self.cells.items() if state == CellState.OCCUPIED)

    @property
    def uncertain_cells(self) -> frozenset[int]:
        return frozenset(cell for cell, state in self.cells.items() if state == CellState.UNCERTAIN)


@dataclass(frozen=True)
class _Sample:
    timestamp: float
    visible_ids: frozenset[int]


class BoardObserver:
    """Estimate cell occupancy from every successfully captured observation."""

    def __init__(self, config: ObserverConfig | None = None) -> None:
        self.config = config or ObserverConfig()
        self._samples: deque[_Sample] = deque()
        self._last_evaluation: float | None = None
        self._stable = {cell: CellState.UNCERTAIN for cell in range(1, 10)}
        self._definitive: dict[int, CellState | None] = {
            cell: None for cell in range(1, 10)
        }
        self._pending: dict[int, tuple[CellState, float]] = {}
        self.state = self._empty_state()

    def update(
        self, visible_ids: Iterable[int], timestamp: float | None = None
    ) -> PhysicalBoardState | None:
        now = time.monotonic() if timestamp is None else timestamp
        visible = frozenset(visible_ids) & frozenset(CELL_IDS)
        self._samples.append(_Sample(now, visible))
        cutoff = now - self.config.window_seconds
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

        if (
            self._last_evaluation is not None
            and now - self._last_evaluation + 1e-9
            < self.config.evaluation_period_seconds
        ):
            return None
        self._last_evaluation = now
        self.state = self._evaluate(now)
        return self.state

    def _evaluate(self, now: float) -> PhysicalBoardState:
        total = len(self._samples)
        ready = total >= self.config.min_valid_samples
        ratios = {
            cell_id_to_cell(marker_id): (
                sum(marker_id in sample.visible_ids for sample in self._samples) / total
                if total else 0.0
            )
            for marker_id in CELL_IDS
        }
        detection = {
            marker_id: (
                sum(marker_id in sample.visible_ids for sample in self._samples) / total
                if total else 0.0
            )
            for marker_id in CELL_IDS
        }

        if not ready:
            self._pending.clear()
        else:
            for cell, ratio in ratios.items():
                observed = self._classify(ratio)
                definitive = self._definitive[cell]
                if observed == CellState.UNCERTAIN:
                    self._pending.pop(cell, None)
                    self._stable[cell] = observed
                    continue
                if definitive is None or observed == definitive:
                    self._stable[cell] = observed
                    self._definitive[cell] = observed
                    self._pending.pop(cell, None)
                    continue
                pending = self._pending.get(cell)
                if pending is None or pending[0] != observed:
                    self._pending[cell] = (observed, now)
                elif now - pending[1] >= self.config.state_change_seconds:
                    self._stable[cell] = observed
                    self._definitive[cell] = observed
                    self._pending.pop(cell, None)

        cells = dict(self._stable) if ready else {
            cell: CellState.UNCERTAIN for cell in range(1, 10)
        }
        return PhysicalBoardState(
            cells=cells,
            visibility_ratio=ratios,
            ready=ready,
            total_samples=total,
            detection_ratio=detection,
        )

    def _classify(self, ratio: float) -> CellState:
        if ratio >= self.config.free_ratio:
            return CellState.FREE
        if ratio <= self.config.occupied_ratio:
            return CellState.OCCUPIED
        return CellState.UNCERTAIN

    def _empty_state(self) -> PhysicalBoardState:
        return PhysicalBoardState(
            cells={cell: CellState.UNCERTAIN for cell in range(1, 10)},
            visibility_ratio={cell: 0.0 for cell in range(1, 10)},
            ready=False,
            total_samples=0,
            detection_ratio={marker_id: 0.0 for marker_id in CELL_IDS},
        )


class ArucoStabilityMetrics:
    """Accumulate detection ratios for operational cell markers."""

    def __init__(self) -> None:
        self.total_samples = 0
        self._counts = {marker_id: 0 for marker_id in CELL_IDS}

    def update(self, visible_ids: Iterable[int]) -> None:
        visible = set(visible_ids)
        self.total_samples += 1
        for marker_id in self._counts:
            if marker_id in visible:
                self._counts[marker_id] += 1

    @property
    def marker_ids(self) -> tuple[int, ...]:
        return CELL_IDS

    def detection_ratio(self, marker_id: int) -> float:
        return self._counts[marker_id] / self.total_samples if self.total_samples else 0.0
