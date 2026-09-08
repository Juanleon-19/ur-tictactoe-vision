from __future__ import annotations

import cv2
import numpy as np
import pytest

from ur_tictactoe.vision.aruco import ARUCO_PROFILES, ArucoDetector, build_detector_parameters

APPROVED_IDS = set(range(10, 19))


def parameter_values(parameters):
    return {name: getattr(parameters, name) for name in dir(parameters)
            if not name.startswith("_") and not callable(getattr(parameters, name))}


def test_robust_full_parameter_contract_is_unchanged_by_glare():
    expected = cv2.aruco.DetectorParameters()
    expected.adaptiveThreshWinSizeStep = 4
    if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
        expected.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if hasattr(expected, "useAruco3Detection"):
        expected.useAruco3Detection = True
    robust = build_detector_parameters("robust")
    glare = build_detector_parameters("robust_glare")
    assert parameter_values(robust) == parameter_values(expected)
    assert parameter_values(build_detector_parameters("robust")) == parameter_values(expected)
    assert ARUCO_PROFILES == ("default", "robust", "robust_glare")
    assert glare is not robust
    assert (glare.adaptiveThreshWinSizeMin, glare.adaptiveThreshWinSizeMax,
            glare.adaptiveThreshWinSizeStep) == (3, 43, 4)
    assert {k for k, v in parameter_values(glare).items()
            if v != parameter_values(robust)[k]} == {"adaptiveThreshWinSizeMax"}
    glare.adaptiveThreshWinSizeMax = 99
    assert robust.adaptiveThreshWinSizeMax == 23


@pytest.mark.parametrize("profile", ARUCO_PROFILES)
def test_profile_detects_marker_and_leaves_original_frame_unchanged(profile):
    frame = np.full((300, 300), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    frame[50:250, 50:250] = cv2.aruco.generateImageMarker(dictionary, 18, 200)
    original = frame.copy()
    assert ArucoDetector("DICT_5X5_50", profile).detect(frame).ids == (18,)
    np.testing.assert_array_equal(frame, original)


def test_default_profile_preserves_opencv_defaults() -> None:
    expected = cv2.aruco.DetectorParameters()
    actual = build_detector_parameters("default")

    assert actual.adaptiveThreshWinSizeStep == expected.adaptiveThreshWinSizeStep
    assert actual.cornerRefinementMethod == expected.cornerRefinementMethod
    if hasattr(expected, "useAruco3Detection"):
        assert actual.useAruco3Detection == expected.useAruco3Detection


def test_robust_profile_uses_supported_conservative_options() -> None:
    parameters = build_detector_parameters("robust")

    assert parameters.adaptiveThreshWinSizeMin == 3
    assert parameters.adaptiveThreshWinSizeMax == 23
    assert parameters.adaptiveThreshWinSizeStep == 4
    if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
        assert parameters.cornerRefinementMethod == cv2.aruco.CORNER_REFINE_SUBPIX
    if hasattr(parameters, "useAruco3Detection"):
        assert parameters.useAruco3Detection is True


def test_detects_generated_marker() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 10, 200)

    canvas = np.full((300, 300), 255, dtype=np.uint8)
    canvas[50:250, 50:250] = marker
    frame = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

    detector = ArucoDetector("DICT_5X5_50")
    result = detector.detect(frame)

    assert result.ids == (10,)
    assert len(result.corners) == 1


def test_returns_empty_result_when_no_marker_exists() -> None:
    frame = np.full((300, 300, 3), 255, dtype=np.uint8)

    detector = ArucoDetector("DICT_5X5_50")
    result = detector.detect(frame)

    assert result.ids == ()
    assert result.corners == ()


def test_detects_all_nine_operational_markers_in_synthetic_image() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    marker_size = 100
    margin = 25
    canvas = np.full((4 * 150 + margin, 4 * 150 + margin), 255, dtype=np.uint8)

    for index, marker_id in enumerate(sorted(APPROVED_IDS)):
        row, column = divmod(index, 4)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
        y = margin + row * 150
        x = margin + column * 150
        canvas[y : y + marker_size, x : x + marker_size] = marker

    result = ArucoDetector("DICT_5X5_50").detect(
        cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    )

    assert result.id_set == APPROVED_IDS
    assert len(result.ids) == 9
