"""Operator widgets kept separate from the game window."""

import tkinter as tk
import customtkinter as ctk

from ur_tictactoe.desktop.commissioning_status import latest_commissioning
from ur_tictactoe.desktop.help_content import SECTIONS, help_text
from ur_tictactoe.desktop.settings import application_directory


class CameraControls(ctk.CTkFrame):
    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="x", padx=12)
        snapshot = application.diagnostic_snapshot()
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="CONFIGURACIÓN DE CÁMARA").pack(side="left", padx=(0, 12))
        ctk.CTkLabel(row, text="Cámara:").pack(side="left")
        self.index = tk.StringVar(value=f"Camera {snapshot.camera_index}")
        self.selector = ctk.CTkComboBox(row, values=[f"Camera {i}" for i in range(6)],
                                      variable=self.index, width=110)
        self.selector.pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Backend:").pack(side="left")
        self.backend = tk.StringVar(value=snapshot.backend)
        self.backend_selector = ctk.CTkOptionMenu(row, values=["AUTO", "DSHOW", "MSMF"],
                                               variable=self.backend, width=95)
        self.backend_selector.pack(side="left", padx=6)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", pady=3)
        self.buttons = []
        for label, command in (
            ("DETECTAR CÁMARAS", lambda: application.detect_cameras(self.backend.get())),
            ("APLICAR CÁMARA", self.apply),
            ("RECONECTAR CÁMARA", application.reconnect_camera),
            ("REINICIAR OBSERVACIÓN", application.reset_board_observation),
        ):
            button = ctk.CTkButton(buttons, text=label, command=command, width=145,
                                  font=ctk.CTkFont(size=11))
            button.pack(side="left", padx=(0, 5))
            self.buttons.append(button)
        self.feedback = ctk.CTkLabel(self, text=application.camera_feedback, height=20,
                                   wraplength=700)
        self.feedback.pack(fill="x")
        self._detected = None

    def apply(self):
        try:
            index = int(self.index.get().removeprefix("Camera ").strip())
            if index < 0:
                raise ValueError
        except ValueError:
            self.application.camera_feedback = "Índice de cámara no válido."
            return
        self.application.apply_camera(index, self.backend.get())

    def refresh(self):
        app = self.application
        self.feedback.configure(text=app.camera_feedback)
        state = "disabled" if app.camera_busy or app.physical_game_active or app.simulation else "normal"
        for widget in [self.selector, self.backend_selector, *self.buttons]:
            widget.configure(state=state)
        if not app.camera_busy and self._detected != app.detected_cameras:
            self._detected = list(app.detected_cameras)
            # configure(values=...) preserves the operator's selection.
            self.selector.configure(values=self._detected)


class HelpPanel(ctk.CTkFrame):
    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="both", expand=True)
        self.general = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self.general.pack(fill="x", padx=12)
        self.section = ctk.CTkOptionMenu(self, values=list(SECTIONS), command=lambda _: self.refresh())
        self.section.pack(anchor="w", padx=12, pady=6)
        self.content = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont("Consolas", 13))
        self.content.pack(fill="both", expand=True, padx=12, pady=6)
        self.report = latest_commissioning(application_directory() / "reports")
        self._text = None
        self.refresh()

    def reload_report(self):
        self.report = latest_commissioning(application_directory() / "reports")
        self.refresh()

    def refresh(self):
        snapshot = self.application.snapshot()
        profile = self.application.diagnostic_snapshot().profile
        label = {"robust": "Robusto", "robust_glare": "Reflejos", "default": "Estándar"}[profile]
        self.general.configure(text=f"ESTADO GENERAL\nCámara: {snapshot.camera_status} · "
                               f"Tablero: {snapshot.board_status} · Robot: {snapshot.robot_status} · Perfil: {label}")
        text = help_text(self.section.get(), snapshot, self.report)
        if text != self._text:
            self.content.configure(state="normal")
            self.content.delete("1.0", "end")
            self.content.insert("1.0", text)
            self.content.configure(state="disabled")
            self._text = text
