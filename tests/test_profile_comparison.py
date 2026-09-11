"""Diagnostic statistics never feed back into physical observation."""

import pytest

from ur_tictactoe.desktop.diagnostics import ProfileMeasurements, profile_comparison
from ur_tictactoe.desktop.help_content import SECTIONS, help_text
from ur_tictactoe.desktop.application import GameApplication
from test_real_backend import make_backend


def test_visibility_per_id_and_frame_rate_use_existing_observations():
    samples = ProfileMeasurements()
    samples.update("robust", {10, 18, 0}, 100)
    samples.update("robust", {10, 11}, 100.5)
    profile, count, elapsed, fps, visibility = samples.snapshot()[0]
    assert (profile, count, elapsed, fps) == ("robust", 2, .5, 2)
    assert visibility == (100, 50, 0, 0, 0, 0, 0, 0, 50)
    samples.select("robust_glare")
    samples.update("robust_glare", {18}, 999)
    assert samples.snapshot()[1][2:4] == (0, None)
    assert len(samples.snapshot()) == 2
    samples.select("robust")
    assert [s[0] for s in samples.snapshot()] == ["robust_glare"]


def test_comparison_is_explicitly_experimental_and_requires_comparable_conditions():
    samples = ProfileMeasurements()
    samples.update("robust", set(range(10, 19)), 0)
    text = profile_comparison(samples.snapshot())
    assert "predeterminado" in text and "experimental" in text
    assert "no demuestran superioridad" in text and "10 s" in text
    assert "Reflejos (experimental): sin muestra" in text
    assert all(f"ID{marker}: 100%" in text for marker in range(10, 19))


def test_backend_comparison_never_adds_reads_detection_or_observer_updates():
    backend = make_backend()
    backend.open()
    backend.tick()
    backend.tick()
    for _ in range(5):
        assert backend.diagnostic_snapshot().profile_samples[0][1] == 2
    assert backend.camera.read_calls == len(backend.detector.frames) == len(backend.observer.visible) == 2
    backend.close()


@pytest.mark.parametrize("change", ["reconnect", "capture_error"])
def test_camera_changes_discard_incomparable_profile_samples(change):
    backend = make_backend()
    backend.open()
    backend.tick()
    if change == "reconnect":
        backend.reconnect_camera()
    else:
        def fail():
            raise RuntimeError("test capture failure")
        backend.camera.read = fail
        backend.tick()
    assert backend.diagnostic_snapshot().profile_samples == ()
    backend.close()


def test_user_help_keeps_commissioning_in_advanced():
    assert SECTIONS == ("CÓMO JUGAR", "INFORMACIÓN TÉCNICA")
    app = GameApplication(simulation=True)
    snapshot = app.snapshot()
    text = help_text("CÓMO JUGAR", snapshot, None)
    for technical in ("C14", "C1", "COMMAND", "STATUS", "Modbus", "URScript"):
        assert technical not in text
    for action in ("REINICIAR SISTEMA", "RECONECTAR CÁMARA", "SALIR", "PolyScope", "9 marcadores"):
        assert action in text
    assert "P_DISCARD" in help_text("Acerca de", snapshot, None)
    assert app.snapshot() == snapshot
    app.close()
