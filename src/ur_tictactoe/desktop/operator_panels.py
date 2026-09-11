"""Compact operator controls, separate from game logic and device ownership."""

import tkinter as tk
import customtkinter as ctk

from ur_tictactoe.desktop.operator_style import theme


class CameraControls(ctk.CTkFrame):
    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="x", padx=14)
        snapshot = application.diagnostic_snapshot()
        normal = ctk.CTkFrame(self, fg_color="transparent")
        normal.pack(fill="x")
        self.advanced_button = ctk.CTkButton(
            normal, text="CONFIGURACIÓN AVANZADA ▸", height=30, width=220,
            fg_color=theme.BORDER, text_color=theme.PRIMARY, command=self.toggle_backend)
        self.advanced_button.pack(side="right")
        self.advanced = ctk.CTkFrame(self, fg_color="transparent")
        self.index = tk.StringVar(value=f"Camera {snapshot.camera_index}")
        self.selector = ctk.CTkComboBox(self.advanced, values=[f"Camera {i}" for i in range(6)],
                                      variable=self.index, width=110)
        self.selector.pack(side="left", padx=(0, 6))
        self.backend = tk.StringVar(value=snapshot.backend)
        self.backend_selector = ctk.CTkOptionMenu(self.advanced, values=["AUTO", "DSHOW", "MSMF"],
                                               variable=self.backend, width=95)
        self.backend_selector.pack(side="left", padx=6)
        self.buttons = []
        for caption, command, parent in (
            ("DETECTAR", lambda: application.detect_cameras(self.backend.get()), self.advanced),
            ("APLICAR", self.apply, self.advanced),
            ("RECONECTAR CÁMARA", application.reconnect_camera, normal),
        ):
            button = ctk.CTkButton(parent, text=caption,
                                  command=lambda action=command: self.invoke_operation(action),
                                  width=165 if parent is normal else 110, height=30,
                                  fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                                  font=ctk.CTkFont("Segoe UI", 11, "bold"))
            button.pack(side="left", padx=(0, 6))
            self.buttons.append(button)
        self.feedback = ctk.CTkLabel(self, text="", height=20, wraplength=650,
                                    font=ctk.CTkFont("Segoe UI", 11), anchor="w")
        self.feedback.pack(fill="x", pady=(2, 4))
        self.profile_message = ""
        self._detected = None
        self.refresh()

    def toggle_backend(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget()
            self.advanced_button.configure(text="CONFIGURACIÓN AVANZADA ▸")
        else:
            self.advanced.pack(fill="x", before=self.feedback, pady=4)
            self.advanced_button.configure(text="CONFIGURACIÓN AVANZADA ▾")

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
        state = "disabled" if app.camera_busy or app.robot_busy or app.physical_game_active or app.simulation or app._closing else "normal"
        for widget in [self.selector, self.backend_selector, *self.buttons]:
            widget.configure(state=state)
        for button in self.buttons:
            button.configure(fg_color=theme.BORDER if state == "disabled" else theme.PRIMARY)
        if not app.camera_busy and self._detected != app.detected_cameras:
            self._detected = list(app.detected_cameras)
            self.selector.configure(values=self._detected)


class RobotControls(ctk.CTkFrame):
    """One explicit system restart action on the home screen."""

    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="x", pady=(8, 0))
        self.restart_button = ctk.CTkButton(self, text="REINICIAR SISTEMA", height=34,
                                           font=ctk.CTkFont("Segoe UI", 11, "bold"),
                                           command=application.restart_system)
        self.restart_button.pack(fill="x")
        self.feedback = ctk.CTkLabel(self, text="", wraplength=280, justify="left",
                                     font=ctk.CTkFont("Segoe UI", 11))
        self.feedback.pack(fill="x", pady=(4, 0))
        self.refresh()

    def refresh(self):
        self.restart_button.configure(state="normal" if self.application.system_restart_allowed else "disabled")
        message = self.application.robot_feedback
        if message == "Consulta de estado sin movimientos.":
            message = ""
        self.feedback.configure(text=message)
