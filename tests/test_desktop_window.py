"""Widget acceptance: requires a working desktop Tcl/Tk, no physical devices."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.tk_app import DesktopWindow, VISION_PROFILES
from ur_tictactoe.desktop import theme
from ur_tictactoe.game import PICARO
from test_real_backend import FakeCamera, FakeModbus, make_backend


def test_friendly_vision_profile_mapping():
    assert VISION_PROFILES == {"Robusto": "robust", "Reflejos": "robust_glare", "Estándar": "default"}


def _widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from _widgets(child)


def _check_product_home(window, *, simulation):
    import customtkinter as ctk
    window.root.update()
    widgets = list(_widgets(window.container))
    buttons = [w.cget("text") for w in widgets if isinstance(w, ctk.CTkButton)]
    assert buttons.count("REINICIAR SISTEMA") == 1
    assert "ACTUALIZAR ESTADO" not in buttons and "RECUPERAR ROBOT" not in buttons
    assert not any(isinstance(w, ctk.CTkCheckBox) for w in widgets)
    assert set(window.home_status_labels) == {"Cámara", "Robot", "Tablero"}
    assert window.picaro_radio.cget("state") == ("normal" if simulation else "disabled")
    radios = {w.cget("text"): w for w in widgets if isinstance(w, ctk.CTkRadioButton)}
    assert set(radios) == {"Experto", "Intermedio", "Pícaro", "Robot", "Humano"}
    assert all(w.winfo_ismapped() for w in radios.values())
    for widget in radios.values():
        assert widget.winfo_y() + widget.winfo_height() <= widget.master.winfo_height()
    for w in _widgets(window.root):
        if isinstance(w, ctk.CTkLabel):
            assert "Proyecto académico" not in w.cget("text")
            assert "Pontificia Universidad Javeriana" not in w.cget("text")
    assert window.exit_button.winfo_ismapped()


def _check_header(window):
    window.root.update()
    assert window._logo_image.cget("size") == (260, 130)
    assert window._logo_image.cget("light_image").size == (632, 316)
    assert window.header.winfo_ismapped()
    assert window.logo_label.winfo_ismapped()
    assert window.title_label.winfo_x() >= window.logo_label.winfo_x() + window.logo_label.winfo_width()
    assert window.mode_badge.winfo_x() >= window.title_label.winfo_x() + window.title_label.winfo_width()
    assert window.mode_badge.winfo_x() + window.mode_badge.winfo_width() <= window.header.winfo_width()
    assert not hasattr(window, "academic_label")
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
        _check_product_home(window, simulation=True)
        assert window.author_footer.cget("text") == "By: Juan Esteban León Saiz"
        before = app.snapshot()
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window._render_diagnostics()
        window.root.update()
        _check_header(window)
        assert window.camera_preview.cget("text") == "CÁMARA NO DISPONIBLE"
        assert app.snapshot() == before
        window.tabs.set("AYUDA / PUESTA EN MARCHA")
        window.help_panel.refresh()
        window.root.update()
        assert "ESTADO GENERAL" in window.help_panel.general.cget("text")
        assert window.help_panel.content.winfo_exists()
        for section in window.help_panel.section.cget("values"):
            window.help_panel.section.set(section)
            window.help_panel.refresh()
            assert window.help_panel.content.winfo_children()
        assert app.snapshot() == before
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        assert window.vision_profile.get() == "Robusto"
        assert window.apply_profile_button.cget("state") == "disabled"
        for button in window.camera_controls.buttons:
            assert button.cget("state") == "disabled"
            button.invoke()
        window.apply_profile_button.invoke()
        assert app.real_backend is None
        assert app.diagnostic_snapshot().profile == "robust"
        assert "Controles de cámara disponibles en SISTEMA REAL" == window.camera_controls.feedback.cget("text")
        assert window.camera_details.values["Marcadores"].cget("text") == "0/9"
        assert window.camera_details.values["Faltantes"].cget("text") == "10, 11, 12, 13, 14, 15, 16, 17, 18"
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
        for geometry in ("900x620", "1366x768"):
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


def _check_profile_live() -> None:
    import numpy as np
    from test_real_backend import RecordingObserver, physical
    from ur_tictactoe.game import HARD

    camera = FakeCamera(None)
    camera.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    backend = make_backend(camera=camera, observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    window = DesktopWindow(app)
    errors = []
    window.root.report_callback_exception = lambda *args: errors.append(args)
    try:
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window.root.update()
        app.update()
        window._render_diagnostics()
        assert window._preview_image is not None
        controls = window.camera_controls
        assert controls.backend_selector.cget("values") == ["AUTO", "DSHOW", "MSMF"]
        assert controls.index.get() == "Camera 0"
        calls = []
        original_apply = app.apply_camera
        app.apply_camera = lambda index, backend: calls.append((index, backend))
        try:
            for label in ("AUTO", "DSHOW", "MSMF"):
                controls.index.set("Camera 2")
                controls.backend.set(label)
                controls.buttons[1].invoke()
                assert calls[-1] == (2, label)
            controls.index.set("invalid")
            controls.buttons[1].invoke()
            assert "no válido" in app.camera_feedback
        finally:
            app.apply_camera = original_apply
        app.detected_cameras = ["Camera 1", "Camera 2"]
        controls.index.set("Camera 0")
        controls.refresh()
        assert controls.selector.cget("values") == ["Camera 1", "Camera 2"]
        assert controls.index.get() == "Camera 0"
        window.vision_profile.set("Reflejos")
        window.apply_profile_button.invoke()
        app.update()
        window._render_diagnostics()
        window.root.update()
        assert window._preview_image is not None
        assert window.active_profile.cget("text") == "Perfil activo: Reflejos"
        assert camera.open_calls == backend.modbus_client.connect_calls == 1
        assert camera.close_calls == 0
        assert backend.modbus_client.close_calls == 1
        for geometry in ("900x620", "1366x768"):
            window.root.geometry(geometry)
            window.root.update()
            assert window.profile_selector.winfo_ismapped()
            assert window.active_profile.winfo_ismapped()
            assert window.camera_details.winfo_ismapped()
            assert window.camera_preview.winfo_height() > 20
            assert window.active_profile.winfo_x() + window.active_profile.winfo_width() <= window.active_profile.master.winfo_width()
        backend.observer = RecordingObserver(physical())
        app.update()
        assert app.new_game(HARD, True)
        controls.refresh()
        assert all(button.cget("state") == "disabled" for button in controls.buttons)
        window.vision_profile.set("Robusto")
        window.apply_profile_button.invoke()
        assert window.profile_feedback.cget("text") == "No se puede cambiar el perfil durante una partida activa."
        assert window.active_profile.cget("text") == "Perfil activo: Reflejos"
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
        _check_product_home(window, simulation=False)
        window._start_game()
        window.root.update()
        feedback = window.robot_controls.feedback
        assert "RECONECTAR CÁMARA" in feedback.cget("text")
        assert feedback.winfo_y() + feedback.winfo_height() <= feedback.master.winfo_height()
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
    assert backend.camera.close_calls == 1
    assert backend.modbus_client.close_calls == 2


def _check_operator_layout():
    import customtkinter as ctk
    from ur_tictactoe.desktop.commissioning_status import CommissioningStatus
    from ur_tictactoe.desktop.operator_guidance import PROBLEMS

    app = GameApplication(True)
    def forbidden(*args, **kwargs):
        raise AssertionError("Help or simulation attempted a hardware operation")
    app.open = app.open_async = app.apply_camera = app.reconnect_camera = forbidden
    app.detect_cameras = app.reset_board_observation = forbidden
    window = DesktopWindow(app)
    errors = []
    window.root.report_callback_exception = lambda *args: errors.append(args)
    try:
        for geometry in ("900x620", "1366x768"):
            window.root.geometry(geometry)
            window.tabs.set("CÁMARA / DIAGNÓSTICO")
            window._render_diagnostics()
            window.root.update()
            _check_header(window)
            for button in [window.apply_profile_button, *window.camera_controls.buttons[2:]]:
                assert button.cget("state") == "disabled"
                button.invoke()
                assert button.winfo_ismapped()
                assert button.winfo_x() + button.winfo_width() <= button.master.winfo_width()
                assert button._text_label.winfo_reqwidth() <= button.winfo_width() - 10
            assert window.camera_preview.winfo_height() > 70
            assert isinstance(window.profile_selector, ctk.CTkSegmentedButton)
            controls = window.camera_controls
            assert not controls.advanced.winfo_ismapped()
            controls.advanced_button.invoke()
            window.root.update()
            assert controls.backend_selector.winfo_ismapped()
            assert controls.selector.winfo_ismapped()
            for button in controls.buttons[:2]:
                assert button.winfo_ismapped()
                assert button.cget("state") == "disabled"
            controls.advanced_button.invoke()
            panel = window.camera_details
            assert panel.detail_button.winfo_ismapped()
            assert panel.comparison_button.winfo_ismapped()
            panel.comparison_button.invoke()
            window.root.update()
            assert panel.detail_window.winfo_exists()
            panel.detail_window.destroy()
            assert panel.detail_button.winfo_rooty() + panel.detail_button.winfo_height() <= panel.winfo_rooty() + panel.winfo_height()
            for value in panel.values.values():
                assert value.winfo_rootx() + value.winfo_width() <= panel.winfo_rootx() + panel.winfo_width()
                assert value.winfo_rooty() + value.winfo_height() <= panel.winfo_rooty() + panel.winfo_height()
            window.tabs.set("AYUDA / PUESTA EN MARCHA")
            help_panel = window.help_panel
            help_panel.history = {f"C{i}": CommissioningStatus("test.json", {f"C{i}": "PASS"}, "date", "sha")
                                  for i in range(1, 5)}
            help_panel.section.set("INFORMACIÓN TÉCNICA")
            help_panel.advanced_section.set("Puesta en marcha")
            help_panel.select_section()
            window.root.update()
            help_panel.procedure_button.invoke()
            assert help_panel.selected_procedure == "C5"
            for step in range(1, 15):
                help_panel.show_procedure(f"C{step}")
                window.root.update_idletasks()
                assert help_panel.content.winfo_children()
            help_panel.section.set("INFORMACIÓN TÉCNICA")
            help_panel.advanced_section.set("Solucionar problema")
            help_panel.select_section()
            for problem in PROBLEMS:
                help_panel.show_problem(problem)
                window.root.update_idletasks()
                assert help_panel.content.winfo_children()
            for section in help_panel.section.cget("values"):
                help_panel.section.set(section)
                help_panel.select_section()
                window.root.update_idletasks()
                assert all(not isinstance(widget, ctk.CTkTextbox)
                           for widget in help_panel.content.winfo_children())
                assert help_panel.content.winfo_width() > 600
            assert app.real_backend is None
        assert not errors
    finally:
        window.root.destroy()
        app.close()


def _check_camera_button_routing():
    import customtkinter as ctk
    from ur_tictactoe.desktop.operator_panels import CameraControls
    app = GameApplication(False, real_backend=make_backend())
    calls = []
    app.detect_cameras = lambda backend: calls.append(("detect", backend))
    app.apply_camera = lambda index, backend: calls.append(("apply", index, backend))
    app.reconnect_camera = lambda: calls.append(("reconnect",))
    app.reset_board_observation = lambda: calls.append(("reset",))
    root = ctk.CTk()
    try:
        controls = CameraControls(root, app)
        controls.index.set("Camera 3")
        controls.backend.set("MSMF")
        for button in controls.buttons:
            button.invoke()
        assert calls == [("detect", "MSMF"), ("apply", 3, "MSMF"), ("reconnect",)]
        assert app.real_backend.camera.open_calls == 0
        assert app.real_backend.modbus_client.connect_calls == 0
    finally:
        root.destroy()
        app.close()


def _check_robot_recovery():
    from test_real_backend import RecordingObserver, physical
    from ur_tictactoe.communication.dashboard_client import DashboardSnapshot
    backend = make_backend(modbus=FakeModbus(connect_error=RuntimeError("offline")),
                           observer=RecordingObserver(physical()))
    app = GameApplication(False, real_backend=backend)
    app.open()
    app.update()
    fresh = FakeModbus()
    backend._modbus_factory = lambda: fresh
    backend._dashboard_client = type("Dashboard", (), {
        "snapshot": lambda self: DashboardSnapshot("DISPONIBLE", "PAUSADO", "IDLE", "fake")
    })()
    window = DesktopWindow(app)
    try:
        window.root.update()
        controls = window.robot_controls
        assert controls.restart_button.cget("text") == "REINICIAR SISTEMA"
        assert app.snapshot().robot_status == "ERROR DE CONEXIÓN"
        button = controls.restart_button
        assert button.winfo_ismapped()
        assert button._text_label.winfo_reqwidth() <= button.winfo_width() - 10
        button.invoke()
        app._robot_worker.join(3)
        assert not app.robot_busy
        assert app.snapshot().robot_status == "LISTO"
        backend.observer = RecordingObserver(physical())
        app.update()
        controls.refresh()
        assert controls.feedback.cget("text") == "SISTEMA LISTO"
        assert backend.camera.open_calls == 1 and backend.camera.close_calls == 0
        assert fresh.commands == [0]
        window.tabs.set("CÁMARA / DIAGNÓSTICO")
        window._render_diagnostics()
        assert "Controlador: READY" in window.robot_diagnostics.cget("text")
        assert "PolyScope: PAUSADO" in window.robot_diagnostics.cget("text")
        assert "camera_open_seconds" in window.camera_details.detail_text
        assert "Dashboard 29999: DISPONIBLE" in window.camera_details.detail_text
    finally:
        window.root.destroy()
        app.close()


def _check_shutdown(route):
    from threading import Event
    from test_explicit_robot_recovery import FakeDashboard
    entered, release = Event(), Event()
    backend = make_backend()
    backend._dashboard_client = FakeDashboard()
    original_open = backend.camera.open
    def blocked_open():
        entered.set()
        assert release.wait(10)
        original_open()
    backend.camera.open = blocked_open
    app = GameApplication(False, real_backend=backend)
    window = DesktopWindow(app)
    calls = []
    cleanup = app.shutdown_all
    def record_cleanup(**kwargs):
        calls.append("shutdown")
        cleanup(**kwargs)
    app.shutdown_all = record_cleanup
    try:
        assert app.open_async() and entered.wait(2)
        assert window.exit_button.cget("command") == window._shutdown_callback
        if route == "exit":
            window.exit_button.invoke()
        else:
            window.root.tk.call(window.root.protocol("WM_DELETE_WINDOW"))
        assert calls == ["shutdown"]
        assert not window._closed and window.root.winfo_exists()
        assert app._closing and not app.shutdown_complete
        assert not app.reconnect_camera()
        release.set()
        cleanup(wait=True)
        window._finish_shutdown()
        assert window._closed and app.shutdown_complete
        assert not app._camera_worker.is_alive()
        assert backend.camera.close_calls == 1
        assert backend.modbus_client.close_calls >= 1
        assert backend._dashboard_client.close_calls == 1
        assert backend.modbus_client.commands == []
    finally:
        release.set()
        cleanup(wait=True)
        if not window._closed:
            window.root.destroy()


def _check_exit():
    _check_shutdown("exit")


def _check_window_x():
    _check_shutdown("x")


@pytest.mark.parametrize("check", ["_check_simulation", "_check_real", "_check_profile_live", "_check_operator_layout", "_check_camera_button_routing", "_check_robot_recovery", "_check_exit", "_check_window_x"])
def test_desktop_process_acceptance(check) -> None:
    # CTk maintains process-global theme/scaling state. Each application launch
    # gets its own process, including the real-widget acceptance checks.
    env = dict(os.environ)
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), str(root / "tests")])
    result = subprocess.run(
        [sys.executable, "-c", "import runpy,sys; runpy.run_path(sys.argv[1])[sys.argv[2]]()",
         str(Path(__file__).resolve()), check],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr, result.stderr
