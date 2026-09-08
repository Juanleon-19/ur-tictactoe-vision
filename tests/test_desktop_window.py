"""Widget acceptance: requires a working desktop Tcl/Tk, no physical devices."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.tk_app import DesktopWindow
from ur_tictactoe.desktop import theme
from ur_tictactoe.game import PICARO
from test_real_backend import FakeCamera, FakeModbus, make_backend


def _check_header(window):
    window.root.update()
    assert window._logo_image.cget("size") == (220, 110)
    assert window._logo_image.cget("light_image").size == (632, 316)
    assert window.header.winfo_ismapped()
    assert window.logo_label.winfo_ismapped()
    assert window.title_label.winfo_x() >= window.logo_label.winfo_x() + window.logo_label.winfo_width()
    assert window.mode_badge.winfo_x() >= window.title_label.winfo_x() + window.title_label.winfo_width()
    assert window.mode_badge.winfo_x() + window.mode_badge.winfo_width() <= window.header.winfo_width()
    assert window.academic_label.winfo_y() + window.academic_label.winfo_height() <= window.header.winfo_height()
    assert window.header.winfo_y() + window.header.winfo_height() <= window.tabs.winfo_y()


def _check_simulation() -> None:
    app = GameApplication(simulation=True)
    window = DesktopWindow(app)
    errors = []
    window.root.report_callback_exception = lambda *args: errors.append(args)
    try:
        window.root.update()
        assert window._logo_image is not None
        _check_header(window)
        assert window.academic_label.cget("text") == "Proyecto académico\nPontificia Universidad Javeriana"
        assert window.author_footer.cget("text") == "By: Juan Esteban León Saiz"
        before = app.snapshot()
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window._render_diagnostics()
        window.root.update()
        _check_header(window)
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
        dimensions = [(b.winfo_width(), b.winfo_height()) for b in window.cell_buttons]
        assert len(set(dimensions)) <= 4  # grid rounding may differ by one pixel
        assert max(w for w, h in dimensions) - min(w for w, h in dimensions) <= 1
        assert max(h for w, h in dimensions) - min(h for w, h in dimensions) <= 1
        assert app.play_human_cell(5)
        for _ in range(4):
            app.update()
        window._render()
        window.root.update()
        for i, value in enumerate(app.snapshot().board):
            if value:
                assert window.cell_buttons[i].cget("fg_color") == (theme.X_COLOR if value == "X" else theme.O_COLOR)
        assert dimensions == [(b.winfo_width(), b.winfo_height()) for b in window.cell_buttons]
        for geometry in ("800x550", "900x620"):
            window.root.geometry(geometry)
            _check_header(window)
            window.tabs.set("CÁMARA / DIAGNÓSTICO")
            _check_header(window)
            window.tabs.set("JUEGO")
        assert window.author_footer.winfo_y() + window.author_footer.winfo_height() <= window.root.winfo_height()
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
        _check_header(window)
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
