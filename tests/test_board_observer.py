from __future__ import annotations

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.board_observer import (
    BoardObserver,
    CellState,
    ObserverConfig,
)
from ur_tictactoe.vision.move_detector import cell_id_to_cell

ALL_IDS = set(CELL_IDS)


def _observer(**overrides) -> BoardObserver:
    values = {
        "window_seconds": 1.0,
        "evaluation_period_seconds": 0.1,
        "state_change_seconds": 0.2,
        "min_valid_samples": 2,
    }
    values.update(overrides)
    return BoardObserver(ObserverConfig(**values))


def _feed(observer: BoardObserver, observations, start=0.0, step=0.1):
    state = None
    for index, ids in enumerate(observations):
        evaluated = observer.update(ids, start + index * step)
        if evaluated is not None:
            state = evaluated
    return state or observer.state


def test_all_stable_ids_produce_free_board_and_mapping() -> None:
    state = _feed(_observer(), [ALL_IDS] * 5)

    assert state.ready
    assert state.free_cells == frozenset(range(1, 10))
    assert state.visibility_ratio[1] == 1.0
    assert state.visibility_ratio[9] == 1.0


def test_brief_loss_does_not_change_free_to_occupied() -> None:
    observer = _observer(window_seconds=1.5)
    _feed(observer, [ALL_IDS] * 10)
    missing_10 = ALL_IDS - {10}
    state = _feed(observer, [missing_10] * 5 + [ALL_IDS] * 12, start=1.0)

    assert 1 not in state.occupied_cells
    assert state.cells[1] == CellState.FREE


def test_persistent_absence_produces_occupied() -> None:
    observer = _observer()
    _feed(observer, [ALL_IDS] * 5)
    state = _feed(observer, [ALL_IDS - {10}] * 16, start=0.5)

    assert state.cells[1] == CellState.OCCUPIED


def test_reappearing_marker_returns_to_free() -> None:
    observer = _observer()
    _feed(observer, [ALL_IDS - {10}] * 15)
    assert observer.state.cells[1] == CellState.OCCUPIED

    state = _feed(observer, [ALL_IDS] * 16, start=1.5)
    assert state.cells[1] == CellState.FREE


def test_intermediate_ratio_is_uncertain() -> None:
    observer = _observer(window_seconds=2.0, min_valid_samples=1)
    observations = [ALL_IDS] * 5 + [ALL_IDS - {10}] * 5
    state = _feed(observer, observations)

    assert state.visibility_ratio[1] == 0.5
    assert state.cells[1] == CellState.UNCERTAIN


def test_readiness_requires_minimum_samples_only() -> None:
    observer = BoardObserver()
    for index in range(2):
        state = observer.update(ALL_IDS, index * 0.3)
        assert not state.ready
        assert state.uncertain_cells == frozenset(range(1, 10))
    state = observer.update(ALL_IDS, 0.6)
    assert state.ready
    assert state.total_samples == 3
    assert state.free_cells == frozenset(range(1, 10))


def test_absences_are_included_in_visibility_history() -> None:
    state = _feed(
        _observer(window_seconds=2.0),
        [ALL_IDS, ALL_IDS - {10}, ALL_IDS, ALL_IDS - {10}],
    )
    assert state.ready
    assert state.total_samples == 4
    assert state.visibility_ratio[1] == 0.5
    assert state.cells[1] == CellState.UNCERTAIN


def test_id18_occasional_flicker_is_absorbed_with_operational_defaults() -> None:
    observer = BoardObserver()
    _feed(observer, [ALL_IDS] * 16)
    for index in range(30):
        ids = ALL_IDS - {18} if index % 5 == 0 else ALL_IDS
        observer.update(ids, 1.6 + index * 0.1)
        assert observer.state.ready
        assert observer.state.cells[9] == CellState.FREE


def test_empty_detections_are_samples_and_window_expires() -> None:
    observer = BoardObserver()
    _feed(observer, [ALL_IDS] * 10)
    state = _feed(observer, [set()] * 30, start=1.0)
    assert state.ready
    assert state.occupied_cells == frozenset(range(1, 10))
    state = observer.update(ALL_IDS, 10.0)
    assert not state.ready
    assert state.total_samples == 1


def test_metrics_only_count_operational_ids() -> None:
    from ur_tictactoe.vision.board_observer import ArucoStabilityMetrics

    metrics = ArucoStabilityMetrics()
    metrics.update(ALL_IDS | {49})
    metrics.update(ALL_IDS - {18})
    assert metrics.marker_ids == CELL_IDS
    assert metrics.total_samples == 2
    assert metrics.detection_ratio(18) == 0.5
    assert metrics.detection_ratio(10) == 1.0


def test_cell_marker_ids_map_to_cells_one_through_nine() -> None:
    assert [cell_id_to_cell(marker_id) for marker_id in CELL_IDS] == list(range(1, 10))
