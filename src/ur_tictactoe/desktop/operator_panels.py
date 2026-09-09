"""Operator widgets kept separate from the game window."""

import tkinter as tk
import customtkinter as ctk

from ur_tictactoe.desktop.operator_style import label, theme


class CameraControls(ctk.CTkFrame):
    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="x", padx=14)
        snapshot = application.diagnostic_snapshot()
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
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
        buttons.pack(fill="x", pady=(6, 2))
        buttons.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="actions")
        self.buttons = []
        for caption, command in (
            ("DETECTAR", lambda: application.detect_cameras(self.backend.get())),
            ("APLICAR CÁMARA", self.apply),
            ("RECONECTAR", application.reconnect_camera),
            ("REINICIAR OBS.", application.reset_board_observation),
        ):
            button = ctk.CTkButton(buttons, text=caption, command=lambda action=command: self.invoke_operation(action), width=130, height=30, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                                  font=ctk.CTkFont("Segoe UI", 11, "bold"))
            button.grid(row=0, column=len(self.buttons), sticky="ew", padx=(0, 6))
            self.buttons.append(button)
        notes = ctk.CTkFrame(self, fg_color="transparent")
        notes.pack(fill="x", pady=(0, 4))
        self.note = label(notes, "Solo para esta sesión", color=theme.TEXT_SECONDARY)
        self.note.configure(height=20)
        self.note.pack(side="left")
        self.feedback = ctk.CTkLabel(notes, text="", height=20, wraplength=630,
                                    font=ctk.CTkFont("Segoe UI", 11))
        self.feedback.pack(side="right", fill="x", expand=True)
        self.profile_message = ""
        self._detected = None
        self.refresh()

    def invoke_operation(self, action):
        self.profile_message = ""
        action()

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
        message = self.profile_message or app.camera_feedback
        if app.simulation:
            message = "Controles de cámara disponibles en SISTEMA REAL"
        elif message == "Solo para esta sesión":
            message = ""
        self.feedback.configure(text=message)

        state = "disabled" if app.camera_busy or app.physical_game_active or app.simulation else "normal"
        for widget in [self.selector, self.backend_selector, *self.buttons]:
            widget.configure(state=state)
        for button in self.buttons:
            button.configure(fg_color=theme.BORDER if state == "disabled" else theme.PRIMARY)
        if not app.camera_busy and self._detected != app.detected_cameras:
            self._detected = list(app.detected_cameras)
            # configure(values=...) preserves the operator's selection.
            self.selector.configure(values=self._detected)
