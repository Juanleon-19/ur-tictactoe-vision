"""Compact, presentation-only diagnostic card."""

import customtkinter as ctk
from ur_tictactoe.desktop.diagnostics import profile_comparison
from ur_tictactoe.desktop.operator_style import label, badge, status_color, PROFILE_LABELS, theme


class DiagnosticPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.CARD_BACKGROUND, corner_radius=12,
                         border_width=1, border_color=theme.BORDER, width=255)
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", padx=12, pady=(6, 4))
        label(heading, "ESTADO", bold=True, color=theme.PRIMARY).pack(side="left")
        self.detail_button = ctk.CTkButton(heading, text="DETALLE", command=self.show_detail,
                                          fg_color=theme.PRIMARY, height=24, width=85)
        self.detail_button.pack(side="right")
        self.comparison_button = ctk.CTkButton(self, text="COMPARAR PERFILES", command=self.show_comparison,
                                               height=24, fg_color=theme.PRIMARY)
        self.comparison_button.pack(fill="x", padx=12, pady=(0, 4))
        self.values = {}
        for name in ("Cámara", "Resolución", "FPS", "Perfil", "Marcadores", "Faltantes", "Tablero", "Iluminación"):
            row = ctk.CTkFrame(self, fg_color="transparent", height=24)
            row.pack(fill="x", padx=12)
            caption = label(row, name, color=theme.TEXT_SECONDARY)
            caption.configure(height=20)
            caption.pack(side="left")
            self.values[name] = badge(row, "—")
            self.values[name].configure(wraplength=140, width=140, height=20)
            self.values[name].pack(side="right")
        self.detail_text = ""
        self.detail_window = None
        self.comparison_text = profile_comparison(())

    def refresh(self, diagnostic, snapshot):
        self.comparison_text = profile_comparison(diagnostic.profile_samples)
        missing = [str(i) for i in range(10, 19) if i not in diagnostic.visible_ids]
        values = {
            "Cámara": f"{diagnostic.camera_index} · {diagnostic.backend}",
            "Resolución": "×".join(map(str, diagnostic.resolution)) if diagnostic.resolution else "—",
            "FPS": f"{diagnostic.fps:.1f}" if diagnostic.fps is not None else "—",
            "Perfil": PROFILE_LABELS[diagnostic.profile], "Marcadores": f"{len(diagnostic.visible_ids)}/9",
            "Faltantes": ", ".join(missing) or "Ninguno", "Tablero": snapshot.board_status,
            "Iluminación": diagnostic.illumination,
        }
        for name, value in values.items():
            color = status_color(value)
            if name == "Cámara":
                color = status_color(diagnostic.camera_status)
            elif name in ("Marcadores", "Faltantes") and missing:
                color = theme.DISABLED if diagnostic.frame is None else theme.WARNING
            self.values[name].configure(text=value, text_color=color)
        self.detail_text = (f"Cámara: {diagnostic.camera_status}\nIDs visibles: "
                            + (", ".join(map(str, diagnostic.visible_ids)) or "Ninguno")
                            + "\nFPS medidos entre capturas de la GUI.\n"
                            + (snapshot.last_error or "Sin errores registrados."))
        def seconds(value):
            return f"{value:.3f} s" if value is not None else "NO DISPONIBLE"

        self.detail_text += (
            f"\n\ncamera_index: {diagnostic.camera_index}\nbackend: {diagnostic.backend}"
            f"\nbackend efectivo: {diagnostic.effective_backend or 'NO DISPONIBLE'}"
            f"\ncamera_open_seconds: {seconds(diagnostic.camera_open_seconds)}"
            f"\nfirst_frame_seconds: {seconds(diagnostic.first_frame_seconds)}"
            f"\ncapture_open_seconds: {seconds(diagnostic.capture_open_seconds)}"
            f"\nconfigure_seconds: {seconds(diagnostic.configure_seconds)}"
            f"\nfirst_frame_read_seconds: {seconds(diagnostic.first_frame_read_seconds)}"
            f"\nApertura en curso: {seconds(diagnostic.opening_seconds)}"
            "\nPrimer frame: desde fin de apertura, incluye espera del tick."
            "\nUSB/OpenCV es independiente de Modbus TCP 502."
            f"\n\nÚltima consulta Modbus: {diagnostic.modbus_status}"
            f"\nControlador STATUS129: {diagnostic.controller_status}"
            f"\n{diagnostic.robot_error or 'Sin error de consulta Modbus.'}"
            f"\nDashboard 29999: {diagnostic.dashboard.availability}"
            f"\nPolyScope: {diagnostic.dashboard.program_state}"
            f"\nRobot mode: {diagnostic.dashboard.robot_mode}"
            f"\n{diagnostic.dashboard.detail}"
            "\nEJECUTANDO no identifica el programa requerido: confirmar en el pendant."
            "\nUna consulta válida no reanuda una partida ni resuelve una entrega incierta."
            "\nCOMMAND0 es acknowledgement/reset del protocolo, NO emergency stop."
        )
        if diagnostic.game_history:
            self.detail_text += "\n\nHISTORIAL DE PARTIDAS CANCELADAS (sesión)\n" + "\n\n".join(diagnostic.game_history)

    def show_detail(self):
        self._show_text("Detalle técnico", self.detail_text)

    def show_comparison(self):
        self._show_text("Robusto / Reflejos — muestra actual", self.comparison_text)

    def _show_text(self, title, contents):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
        self.detail_window = ctk.CTkToplevel(self)
        self.detail_window.title(title)
        self.detail_window.geometry("660x420")
        self.detail_window.transient(self.winfo_toplevel())
        text = ctk.CTkTextbox(self.detail_window, wrap="word", font=ctk.CTkFont("Segoe UI", 12))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", contents)
        text.configure(state="disabled")
