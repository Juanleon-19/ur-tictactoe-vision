"""Run the preview renderer with real frames but no native windows or hardware."""

import numpy as np
import pytest

from ur_tictactoe.commissioning import preview
from ur_tictactoe.vision.aruco import DetectionResult


@pytest.mark.parametrize("key", [ord("c"), ord("C"), ord("q"), ord("Q"), 27])
def test_preview_renders_operational_ids_and_closes(monkeypatch, key):
    events, labels, drawn_ids = [], [], []
    monkeypatch.setattr(preview.cv2, "namedWindow", lambda *args: events.append("open"))
    monkeypatch.setattr(preview.cv2, "imshow", lambda *args: events.append("frame"))
    def wait(delay):
        assert delay == 15
        return key
    monkeypatch.setattr(preview.cv2, "waitKey", wait)
    monkeypatch.setattr(preview.cv2, "getWindowProperty", lambda *args: 1)
    monkeypatch.setattr(preview.cv2, "destroyWindow", lambda *args: events.append("close"))
    original_draw, original_text = preview.draw_detections, preview.cv2.putText

    def draw(frame, detection):
        drawn_ids.extend(detection.ids)
        return original_draw(frame, detection)

    def put_text(frame, text, *args):
        labels.append(text)
        return original_text(frame, text, *args)

    monkeypatch.setattr(preview, "draw_detections", draw)
    monkeypatch.setattr(preview.cv2, "putText", put_text)
    frame = np.zeros((160, 320, 3), dtype=np.uint8)
    corners = np.array([[[10, 10], [30, 10], [30, 30], [10, 30]]], dtype=np.float32)
    detection = DetectionResult((corners, corners), (0, 18))
    with preview.VisionPreview(profile="robust_glare") as window:
        assert window.show(frame, detection, 28.65) == key
    assert drawn_ids == [18]
    assert "Profile: robust_glare" in labels
    assert any("Click preview for focus" in text for text in labels)
    assert any("Visibles 1/9: [18]" in text for text in labels)
    assert any("Missing IDs: [10, 11, 12, 13, 14, 15, 16, 17]" in text for text in labels)
    assert any("FPS: 28.6" in text or "FPS: 28.7" in text for text in labels)
    assert events == ["open", "frame", "close"]
    assert not frame.any()  # Production renderer copies its input.


@pytest.mark.parametrize("raises", [False, True])
def test_x_close_is_latched_before_imshow_and_never_recreates_window(monkeypatch, raises):
    events = []
    alive = [True]
    monkeypatch.setattr(preview.cv2, "namedWindow", lambda *args: events.append("open"))
    monkeypatch.setattr(preview.cv2, "imshow", lambda *args: events.append("frame"))
    monkeypatch.setattr(preview.cv2, "waitKey", lambda _: -1)
    monkeypatch.setattr(preview.cv2, "destroyWindow", lambda *args: events.append("destroy"))
    def visible(*args):
        if not alive[0] and raises:
            raise preview.cv2.error("Native window destroyed")
        return 1 if alive[0] else -1
    monkeypatch.setattr(preview.cv2, "getWindowProperty", visible)
    with preview.VisionPreview(profile="robust") as window:
        frame = np.zeros((160, 320, 3), dtype=np.uint8)
        result = DetectionResult((), ())
        assert window.show(frame, result, 30) == 255
        alive[0] = False  # X while a frame is being acquired/detected.
        assert window.show(frame, result, 30) == 27
        assert window.poll_key() == 27
        assert window.show(frame, result, 30) == 27
    assert events == ["open", "frame"]
