"""Compact, presentation-only diagnostic card."""

import customtkinter as ctk
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

    def refresh(self, diagnostic, snapshot):
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

    def show_detail(self):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
        self.detail_window = ctk.CTkToplevel(self)
        self.detail_window.title("Detalle técnico")
        self.detail_window.geometry("600x260")
        self.detail_window.transient(self.winfo_toplevel())
        text = ctk.CTkTextbox(self.detail_window, wrap="word", font=ctk.CTkFont("Segoe UI", 12))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", self.detail_text)
        text.configure(state="disabled")
