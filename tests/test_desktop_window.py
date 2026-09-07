"""Widget acceptance: requires a working desktop Tcl/Tk, no physical devices."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.tk_app import DesktopWindow
from ur_tictactoe.game import PICARO
from test_real_backend import FakeCamera, FakeModbus, make_backend


def _check_simulation() -> None:
    app = GameApplication(simulation=True)
    window = DesktopWindow(app)
    errors = []
    window.root.report_callback_exception = lambda *args: errors.append(args)
    try:
        window.root.update()
        assert window._logo_image is not None
        before = app.snapshot()
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window._render_diagnostics()
        window.root.update()
        assert window.camera_preview.cget("text") == "CÁMARA NO DISPONIBLE"
        assert app.snapshot() == before
        window.tabs.set("JUEGO")
        assert app.new_game(PICARO, True, seed=7)
        window._show_game()
        window._render()
        window.root.update()
        assert len(window.cell_buttons) == 9
        window.cell_buttons[0].focus_set()
        window._toggle_human_picaro()
        assert window._picaro_selecting
        window._toggle_human_picaro()
        assert not window._picaro_selecting
        assert app.snapshot().human_picaro_available
        assert not errors
    finally:
        window.root.destroy()
        app.close()


def _check_real() -> None:
    backend = make_backend(
        camera=FakeCamera(None, RuntimeError("camera absent")),
        modbus=FakeModbus(connect_error=RuntimeError("robot absent")),
    )
    app = GameApplication(simulation=False, real_backend=backend)
    assert not app.open()
    window = DesktopWindow(app)
    try:
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window._render_diagnostics()
        window.root.update()
        assert window.camera_preview.cget("text") == "CÁMARA NO DISPONIBLE"
        assert not app.new_game(PICARO, True)
        assert not app.play_human_picaro(1)
    finally:
        window.root.destroy()
        app.close()
    assert backend.camera.close_calls == backend.modbus_client.close_calls == 1


@pytest.mark.parametrize("check", ["_check_simulation", "_check_real"])
def test_desktop_process_acceptance(check) -> None:
    # CTk maintains process-global theme/scaling state. Each application launch
    # gets its own process, including the real-widget acceptance checks.
    env = dict(os.environ)
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), str(root / "tests")])
    result = subprocess.run(
        [sys.executable, "-c", "import runpy,sys; runpy.run_path(sys.argv[1])[sys.argv[2]]()",
         str(Path(__file__).resolve()), check],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr, result.stderr
