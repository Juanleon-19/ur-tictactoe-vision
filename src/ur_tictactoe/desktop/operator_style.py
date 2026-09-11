"""Presentation primitives shared by operator screens, independent of hardware."""

import customtkinter as ctk
from ur_tictactoe.desktop import theme

PROFILE_LABELS = {"robust": "Robusto", "robust_glare": "Reflejos", "default": "Estándar"}
STATUS_COLORS = {
    "PASS": theme.SUCCESS, "FAIL": theme.ERROR, "BLOCKED": theme.WARNING,
    "SKIPPED": theme.DISABLED, "PENDIENTE": theme.DISABLED,
}


def status_color(value):
    if value in STATUS_COLORS:
        return STATUS_COLORS[value]
    value = value.upper()
    if value == "MOVIMIENTO FÍSICO":
        return theme.ERROR
    if value in ("HANDSHAKE SIN MOVIMIENTO ESPERADO", "BLOQUEADO / PENDIENTE"):
        return theme.WARNING
    if "ERROR" in value:
        return theme.ERROR
    if any(word in value for word in ("SIMULAD", "NO DISPONIBLE", "NO CONECT", "NO CONFIGUR", "DESCONOCIDO", "—")):
        return theme.DISABLED
    if any(word in value for word in ("NO LISTO", "INCIERTO", "ESPERANDO", "REFLEJO", "INICIALIZANDO", "BUSY", "DONE", "PAUSADO", "DETENIDO", "RECUPERACIÓN", "EN MOVIMIENTO")):
        return theme.WARNING
    return theme.SUCCESS


def card(parent, title):
    frame = ctk.CTkFrame(parent, fg_color=theme.CARD_BACKGROUND, corner_radius=12,
                         border_width=1, border_color=theme.BORDER)
    heading = label(frame, title, bold=True, color=theme.PRIMARY)
    heading.configure(height=22)
    heading.pack(anchor="w", padx=14, pady=(8, 4))
    return frame


def label(parent, text, *, bold=False, color=theme.TEXT_PRIMARY):
    widget = ctk.CTkLabel(parent, text=text, anchor="w", justify="left",
                          font=ctk.CTkFont("Segoe UI", 12, "bold" if bold else "normal"),
                          text_color=color)
    return widget


def badge(parent, text):
    return ctk.CTkLabel(parent, text=text, corner_radius=6, height=24,
                       fg_color=theme.BACKGROUND, text_color=status_color(text),
                       font=ctk.CTkFont("Segoe UI", 11, "bold"))


def paragraph(parent, text):
    widget = label(parent, text)
    widget.configure(wraplength=650, height=20)
    widget.pack(fill="x", padx=14, pady=(2, 8))
    # Parent width is fixed by the layout, avoiding text-driven resize feedback.
    parent.bind("<Configure>", lambda event: widget.configure(
        wraplength=max(80, event.width / widget._get_widget_scaling() - 32)), add="+")
    return widget
