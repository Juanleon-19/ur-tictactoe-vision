from __future__ import annotations

import pytest

from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.game import HARD, Board, O, X, choose_move
from ur_tictactoe.vision.move_detector import (
    HumanMoveDetector,
    cell_id_to_cell,
    cell_to_marker_id,
)

ALL_VISIBLE = set(CELL_IDS)


@pytest.mark.parametrize(
    ("marker_id", "cell"),
    [(10, 1), (14, 5), (18, 9)],
)
def test_cell_id_to_cell(marker_id: int, cell: int) -> None:
    assert cell_id_to_cell(marker_id) == cell
    assert cell_to_marker_id(cell) == marker_id


def test_all_markers_visible_returns_none() -> None:
    assert HumanMoveDetector().update(ALL_VISIBLE, True, set()) is None


def test_single_missing_frame_returns_none() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None


def test_same_disappearance_for_n_minus_one_frames_returns_none() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None


def test_same_disappearance_for_n_frames_returns_cell() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    results = [detector.update(ALL_VISIBLE - {14}, True, set()) for _ in range(3)]
    assert results == [None, None, 5]


def test_marker_reappearing_resets_candidate() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    detector.update(ALL_VISIBLE - {14}, True, set())
    detector.update(ALL_VISIBLE - {14}, True, set())
    assert detector.update(ALL_VISIBLE, True, set()) is None
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None


def test_frame_not_ready_returns_none() -> None:
    detector = HumanMoveDetector(stable_frames=1)
    assert detector.update(ALL_VISIBLE - {14}, False, set()) is None


def test_losing_frame_ready_resets_debounce() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    detector.update(ALL_VISIBLE - {14}, True, set())
    detector.update(ALL_VISIBLE - {14}, True, set())
    detector.update(ALL_VISIBLE - {14}, False, set())
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None


def test_two_new_missing_ids_are_rejected_and_reset() -> None:
    detector = HumanMoveDetector(stable_frames=2)
    assert detector.update(ALL_VISIBLE - {14, 15}, True, set()) is None
    assert detector.update(ALL_VISIBLE - {14}, True, set()) is None


def test_occupied_cells_do_not_generate_move() -> None:
    detector = HumanMoveDetector(stable_frames=2)
    for _ in range(3):
        assert detector.update(ALL_VISIBLE - {10, 14}, True, {1, 5}) is None


def test_new_disappearance_after_occupied_cells_returns_next_cell() -> None:
    detector = HumanMoveDetector(stable_frames=2)
    visible = ALL_VISIBLE - {10, 14, 15}
    assert detector.update(visible, True, {1, 5}) is None
    assert detector.update(visible, True, {1, 5}) == 6


def test_confirmed_move_is_not_repeated_before_board_update() -> None:
    detector = HumanMoveDetector(stable_frames=2)
    visible = ALL_VISIBLE - {14}
    assert detector.update(visible, True, set()) is None
    assert detector.update(visible, True, set()) == 5
    assert detector.update(visible, True, set()) is None
    assert detector.update(visible, True, set()) is None


@pytest.mark.parametrize("stable_frames", [0, -1, True])
def test_invalid_stable_frames_raises_clear_error(stable_frames: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        HumanMoveDetector(stable_frames)


def test_unknown_marker_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown cell marker"):
        HumanMoveDetector().update(ALL_VISIBLE | {99}, True, set())


def test_invalid_occupied_cell_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid occupied cell"):
        HumanMoveDetector().update(ALL_VISIBLE, True, {0})


def test_realistic_hand_occlusion_confirms_only_cell_five() -> None:
    detector = HumanMoveDetector(stable_frames=5)
    results = [
        detector.update(ALL_VISIBLE, True, set()),
        detector.update(ALL_VISIBLE - {12, 14}, True, set()),
        detector.update(ALL_VISIBLE - {14}, True, set()),
    ]
    results.extend(
        detector.update(ALL_VISIBLE - {14}, True, set()) for _ in range(4)
    )
    assert [result for result in results if result is not None] == [5]


def test_detector_output_can_drive_game_engine() -> None:
    detector = HumanMoveDetector(stable_frames=3)
    board = Board()
    visible = ALL_VISIBLE - {14}

    human_move = None
    for _ in range(3):
        human_move = detector.update(visible, True, set())

    assert human_move == 5
    board.make_move(human_move, X)
    robot_move = choose_move(board, O, X, HARD, seed=42)

    assert robot_move in range(1, 10)
    assert robot_move in board.available_moves()
    assert robot_move != 5
