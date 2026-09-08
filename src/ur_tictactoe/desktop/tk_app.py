"""Modern CustomTkinter interface for the MVP desktop application."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from PIL import Image
from pathlib import Path

from ur_tictactoe.desktop.application import GameApplication
from ur_tictactoe.desktop.assets import optional_asset
from ur_tictactoe.desktop.settings import load_app_config
from ur_tictactoe.desktop import theme
from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.game import (
    DRAW,
    HARD,
    HUMAN,
    HUMAN_WINS,
    INTERMEDIATE,
    PICARO,
    ROBOT_WINS,
)
from ur_tictactoe.runtime import RuntimeState

STATE_LABELS = {
    RuntimeState.WAITING_HUMAN: "Esperando jugada humana",
    RuntimeState.WAITING_ROBOT: "Preparando jugada del robot",
    RuntimeState.ROBOT_BUSY: "Robot en movimiento",
    RuntimeState.VERIFYING_ROBOT: "Verificando jugada",
    RuntimeState.GAME_OVER: "Partida terminada",
    RuntimeState.ERROR: "Error",
}
RESULT_LABELS = {ROBOT_WINS: "GANÓ EL ROBOT", HUMAN_WINS: "GANÓ EL HUMANO", DRAW: "EMPATE"}
VISION_PROFILES = {"Robusto": "robust", "Reflejos": "robust_glare", "Estándar": "default"}
PROFILE_LABELS = {profile: label for label, profile in VISION_PROFILES.items()}


class CellButton(ctk.CTkButton):
    """An empty cell has no text label; focus the widget itself."""

    def focus_set(self) -> None:
        tk.Misc.focus_set(self)


class DesktopWindow:
    def __init__(self, application: GameApplication) -> None:
        ctk.set_appearance_mode("light")
        self.application = application
        self.root = ctk.CTk(fg_color=theme.BACKGROUND)
        self.root.title("Robot Triqui")
        self.root.geometry(self._centered_geometry(900, 620))
        self.root.minsize(800, 550)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.author_footer = ctk.CTkLabel(
            self.root, text="By: Juan Esteban León Saiz", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont("Segoe UI", 10), height=20,
        )
        self.author_footer.grid(row=2, column=0, sticky="e", padx=20)
        game_tab = self.tabs.add("JUEGO")
        game_tab.grid_rowconfigure(0, weight=1)
        game_tab.grid_columnconfigure(0, weight=1)
        diagnostic_tab = self.tabs.add("CÁMARA / DIAGNÓSTICO")
        vision_controls = ctk.CTkFrame(diagnostic_tab, fg_color="transparent")
        vision_controls.pack(fill="x", padx=12, pady=(6, 0))
        ctk.CTkLabel(vision_controls, text="Perfil de visión:").pack(side="left", padx=(0, 8))
        self.vision_profile = tk.StringVar(
            value=PROFILE_LABELS[application.diagnostic_snapshot().profile]
        )
        self.profile_selector = ctk.CTkOptionMenu(
            vision_controls, values=list(VISION_PROFILES), variable=self.vision_profile,
            width=115,
        )
        self.profile_selector.pack(side="left")
        self.apply_profile_button = ctk.CTkButton(
            vision_controls, text="APLICAR PERFIL", command=self._apply_vision_profile,
            width=130,
        )
        self.apply_profile_button.pack(side="left", padx=10)
        self.active_profile = ctk.CTkLabel(
            vision_controls, text=f"Perfil activo: {self.vision_profile.get()}",
            text_color=theme.PRIMARY,
        )
        self.active_profile.pack(side="left")
        self.profile_feedback = ctk.CTkLabel(
            diagnostic_tab, text="Solo para esta sesión", text_color=theme.TEXT_SECONDARY,
            height=20,
        )
        self.profile_feedback.pack(fill="x", padx=12)
        self.camera_preview = ctk.CTkLabel(diagnostic_tab, text="CÁMARA NO DISPONIBLE", height=1)
        self.camera_details = ctk.CTkLabel(diagnostic_tab, text="", justify="left")
        self.camera_details.pack(side="bottom", fill="x", padx=12, pady=6)
        self.camera_preview.pack(fill="both", expand=True, padx=12, pady=6)
        self._preview_source = None
        self._preview_image = None
        # CTkLabel image=None leaves the previous Tcl image attached.
        self._empty_preview = ctk.CTkImage(Image.new("RGBA", (1, 1)), size=(1, 1))
        self.container = ctk.CTkFrame(game_tab, fg_color="transparent")
        self.container.grid(row=0, column=0, sticky="nsew", padx=34, pady=(8, 16))
        self._logo_image: ctk.CTkImage | None = None
        self._header()
        self.cell_buttons: list[ctk.CTkButton] = []
        self._picaro_selecting = False
        self._show_home()
        self.root.after(self.application.config.update_interval_ms, self._tick)

    def run(self) -> None:
        self.root.mainloop()

    def _centered_geometry(self, width: int, height: int) -> str:
        x = max((self.root.winfo_screenwidth() - width) // 2, 0)
        y = max((self.root.winfo_screenheight() - height) // 2, 0)
        return f"{width}x{height}+{x}+{y}"

    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()
        self.cell_buttons = []

    def _header(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header = header
        header.grid(row=0, column=0, sticky="ew", padx=34, pady=(12, 0))
        header.grid_columnconfigure(1, weight=1)
        logo = optional_asset("assets/javeriana_logo.png")
        if logo:
            with Image.open(logo) as source:
                image = source.copy()
            # Keep full-resolution pixels for high-DPI displays; scale uniformly.
            size = (220, round(image.height * 220 / image.width))
            self._logo_image = ctk.CTkImage(image, size=size)
            self.logo_label = ctk.CTkLabel(header, text="", image=self._logo_image)
            self.logo_label.grid(
                row=0, column=0, rowspan=3, padx=(0, 14)
            )
        self.title_label = ctk.CTkLabel(
            header, text="ROBOT TRIQUI", font=ctk.CTkFont("Segoe UI", 26, "bold"),
            text_color=theme.PRIMARY,
        )
        self.title_label.grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(
            header, text="Sistema autónomo de juego", font=ctk.CTkFont("Segoe UI", 14),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=1, sticky="nw")
        self.academic_label = ctk.CTkLabel(
            header, text="Proyecto académico\nPontificia Universidad Javeriana",
            justify="left", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont("Segoe UI", 12),
        )
        self.academic_label.grid(row=2, column=1, sticky="nw", pady=(6, 0))
        simulated = self.application.simulation
        self.mode_badge = ctk.CTkLabel(
            header, text=f"  {'SIMULACIÓN' if simulated else 'SISTEMA REAL'}  ", height=28,
            corner_radius=14, fg_color="#E6EFF8" if simulated else "#E8F3EC",
            text_color=theme.PRIMARY if simulated else theme.SUCCESS,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
        )
        self.mode_badge.grid(row=0, column=2, rowspan=2, sticky="e")

    def _show_home(self) -> None:
        self._clear()
        self.container.grid_rowconfigure(1, weight=1)
        self.container.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        self.difficulty = tk.StringVar(value=HARD)
        self.human_first = tk.BooleanVar(value=False)

        config = self._card("CONFIGURACIÓN", 0)
        self._field(config, "Modo de juego")
        self._radio(config, "Experto", self.difficulty, HARD).pack(anchor="w", pady=3)
        self._radio(config, "Intermedio", self.difficulty, INTERMEDIATE).pack(anchor="w", pady=3)
        self.picaro_radio = ctk.CTkRadioButton(
            config, text="Pícaro", variable=self.difficulty, value=PICARO,
            state="normal" if self.application.simulation else "disabled",
            text_color_disabled=theme.DISABLED, font=ctk.CTkFont("Segoe UI", 12),
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
        )
        self.picaro_radio.pack(anchor="w", pady=3)
        self.picaro_note = ctk.CTkLabel(
            config, text="", text_color=theme.WARNING,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
        )
        self.picaro_note.pack(anchor="w", pady=(2, 0))
        self.difficulty.trace_add("write", self._update_picaro_note)
        self._field(config, "Quién inicia", (18, 6))
        self._radio(config, "Robot", self.human_first, False).pack(anchor="w", pady=3)
        self._radio(config, "Humano", self.human_first, True).pack(anchor="w", pady=3)

        status = self._card("ESTADO DEL SISTEMA", 1)
        snapshot = self.application.snapshot()
        self._status_row(status, "Cámara", snapshot.camera_status)
        self._status_row(status, "Robot", snapshot.robot_status)
        self._status_row(status, "Tablero", snapshot.board_status)

        footer = ctk.CTkFrame(self.container, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer, text="Pontificia Universidad Javeriana",
            justify="left", text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont("Segoe UI", 11),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer, text="INICIAR PARTIDA", command=self._start_game, width=220, height=48,
            corner_radius=8, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
        ).grid(row=0, column=1, sticky="e")

    def _card(self, title: str, column: int) -> ctk.CTkFrame:
        shell = ctk.CTkFrame(
            self.container, fg_color=theme.CARD_BACKGROUND, border_color=theme.BORDER,
            border_width=1, corner_radius=12,
        )
        shell.grid(row=1, column=column, sticky="nsew", padx=(0, 9) if column == 0 else (9, 0))
        ctk.CTkLabel(
            shell, text=title, font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=theme.PRIMARY,
        ).pack(anchor="w", padx=24, pady=(22, 14))
        content = ctk.CTkFrame(shell, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 22))
        return content

    def _show_game(self) -> None:
        self._clear()
        self.container.grid_rowconfigure(1, weight=1)
        self.container.grid_columnconfigure(0, weight=3, uniform="game")
        self.container.grid_columnconfigure(1, weight=2, uniform="game")
        board = ctk.CTkFrame(
            self.container, fg_color=theme.CARD_BACKGROUND, corner_radius=12,
            border_color=theme.BORDER, border_width=1,
        )
        board.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        board.grid_rowconfigure((0, 1, 2), weight=1, uniform="board")
        board.grid_columnconfigure((0, 1, 2), weight=1, uniform="board")
        for index in range(9):
            cell = ctk.CTkFrame(board, width=110, height=110, fg_color="transparent")
            cell.grid(row=index // 3, column=index % 3, sticky="nsew", padx=7, pady=7)
            cell.grid_propagate(False)
            cell.grid_rowconfigure(0, weight=1)
            cell.grid_columnconfigure(0, weight=1)
            button = CellButton(
                cell, text="", command=lambda cell=index + 1: self._play_cell(cell),
                corner_radius=10, border_width=1, border_color=theme.BORDER,
                fg_color=theme.BACKGROUND, hover_color="#E6EDF5",
                font=ctk.CTkFont("Segoe UI", 48, "bold"), width=110, height=110,
            )
            button.grid(row=0, column=0, sticky="nsew")
            self.cell_buttons.append(button)

        info = ctk.CTkFrame(
            self.container, fg_color=theme.CARD_BACKGROUND, corner_radius=12,
            border_color=theme.BORDER, border_width=1,
        )
        info.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(
            info, text="INFORMACIÓN", font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=theme.PRIMARY,
        ).pack(anchor="w", padx=24, pady=(22, 14))
        self.info = ctk.CTkLabel(
            info, text="", justify="left", anchor="w", font=ctk.CTkFont("Segoe UI", 12),
            text_color=theme.TEXT_PRIMARY,
        )
        self.info.pack(fill="x", padx=24)
        self.symbol_legend = ctk.CTkLabel(
            info, text="", justify="left", anchor="w",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=theme.TEXT_SECONDARY,
        )
        self.symbol_legend.pack(fill="x", padx=24, pady=(12, 0))
        self.picaro_status = ctk.CTkLabel(
            info, text="", justify="left", anchor="w",
            font=ctk.CTkFont("Segoe UI", 11), text_color=theme.TEXT_PRIMARY,
        )
        self.picaro_status.pack(fill="x", padx=24, pady=(12, 0))
        self.picaro_button = ctk.CTkButton(
            info, text="USAR PÍCARO", command=self._toggle_human_picaro,
            width=150, height=34, corner_radius=7, fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
        )
        self.picaro_button.pack(anchor="w", padx=24, pady=(8, 0))
        status = ctk.CTkFrame(info, fg_color="transparent")
        status.pack(fill="x", padx=24, pady=(18, 8))
        self.status_labels = {name: self._status_row(status, name, "") for name in ("Cámara", "Robot", "Tablero")}
        self.result_label = ctk.CTkLabel(
            info, text="", font=ctk.CTkFont("Segoe UI", 18, "bold"), text_color=theme.PRIMARY,
        )
        self.result_label.pack(pady=(10, 2))
        self.error_label = ctk.CTkLabel(
            info, text="", wraplength=260, text_color=theme.ERROR,
            font=ctk.CTkFont("Segoe UI", 11),
        )
        self.error_label.pack(padx=20)
        controls = ctk.CTkFrame(self.container, fg_color="transparent")
        controls.grid(row=2, column=0, columnspan=2, sticky="e", pady=(18, 0))
        self._secondary(controls, "NUEVA PARTIDA").pack(side="left", padx=6)
        self._secondary(controls, "VOLVER AL INICIO").pack(side="left", padx=6)
        self._render()

    def _field(self, parent: ctk.CTkFrame, text: str, pady: tuple[int, int] = (4, 6)) -> None:
        ctk.CTkLabel(
            parent, text=text, font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=pady)

    def _radio(self, parent: ctk.CTkFrame, text: str, variable: tk.Variable, value: object) -> ctk.CTkRadioButton:
        return ctk.CTkRadioButton(
            parent, text=text, variable=variable, value=value, fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER, font=ctk.CTkFont("Segoe UI", 12),
            text_color=theme.TEXT_PRIMARY,
        )

    def _status_row(self, parent: ctk.CTkFrame, name: str, value: str) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=8)
        dot = ctk.CTkLabel(row, text="●", width=20, font=ctk.CTkFont("Segoe UI", 15))
        dot.pack(side="left")
        ctk.CTkLabel(row, text=name, width=90, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        label = ctk.CTkLabel(row, text=value, anchor="e", font=ctk.CTkFont("Segoe UI", 11, "bold"))
        label.pack(side="right")
        color = self._status_color(value)
        dot.configure(text_color=color)
        label.configure(text_color=color)
        return dot, label

    def _secondary(self, parent: ctk.CTkFrame, text: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=lambda: self.root.after(50, self._show_home),
            width=165, height=42,
            fg_color="transparent", hover_color="#E6EDF5", border_width=1,
            border_color=theme.PRIMARY, text_color=theme.PRIMARY,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
        )

    def _start_game(self) -> None:
        self.application.new_game(self.difficulty.get(), self.human_first.get())
        self.root.after(50, self._show_game)

    def _update_picaro_note(self, *_args: object) -> None:
        selected = self.difficulty.get() == PICARO and self.application.simulation
        self.picaro_note.configure(text="PÍCARO · SOLO SIMULACIÓN" if selected else "")

    def _play_cell(self, cell: int) -> None:
        if self._picaro_selecting:
            if self.application.play_human_picaro(cell):
                self._picaro_selecting = False
        else:
            self.application.play_human_cell(cell)
        self._render()

    def _toggle_human_picaro(self) -> None:
        self._picaro_selecting = not self._picaro_selecting
        self._render()

    def _tick(self) -> None:
        self.application.update()
        if self.tabs.get() == "CÁMARA / DIAGNÓSTICO":
            self._render_diagnostics()
        if self.cell_buttons and self.cell_buttons[0].winfo_exists():
            self._render()
        self.root.after(self.application.config.update_interval_ms, self._tick)

    def _apply_vision_profile(self) -> None:
        applied = self.application.set_aruco_profile(VISION_PROFILES[self.vision_profile.get()])
        self.profile_feedback.configure(
            text="Perfil aplicado · Solo para esta sesión" if applied
            else self.application.profile_change_error,
            text_color=theme.TEXT_SECONDARY if applied else theme.ERROR,
        )
        self._render_diagnostics()

    def _render_diagnostics(self) -> None:
        snapshot = self.application.diagnostic_snapshot()
        self.active_profile.configure(text=f"Perfil activo: {PROFILE_LABELS[snapshot.profile]}")
        if snapshot.frame is None:
            self.camera_preview.configure(image=self._empty_preview, text="CÁMARA NO DISPONIBLE")
            self._preview_source = None
            self._preview_image = None
        elif snapshot.frame is not self._preview_source:
            preview = Image.fromarray(snapshot.frame)
            preview.thumbnail((
                min(640, max(1, self.camera_preview.winfo_width())),
                min(360, max(1, self.camera_preview.winfo_height())),
            ))
            self._preview_image = ctk.CTkImage(preview, size=preview.size)
            self._preview_source = snapshot.frame
            self.camera_preview.configure(image=self._preview_image, text="")
        resolution = " × ".join(map(str, snapshot.resolution)) if snapshot.resolution else "—"
        cells = "   ".join(f"{cell}: {state.value}" for cell, state in enumerate(snapshot.cells, 1))
        missing = sorted(set(CELL_IDS).difference(snapshot.visible_ids))
        self.camera_details.configure(
            text=f"Cámara: {snapshot.camera_status} | {resolution}\n"
                 f"IDs visibles ({len(snapshot.visible_ids)}/9): {', '.join(map(str, snapshot.visible_ids)) or '—'}\n"
                 f"IDs faltantes: {', '.join(map(str, missing)) or '—'}\n{cells}",
            wraplength=760,
        )

    def _render(self) -> None:
        snapshot = self.application.snapshot()
        turn = "HUMANO" if snapshot.turn == HUMAN else "ROBOT" if snapshot.turn else "—"
        difficulty = (
            "EXPERTO"
            if snapshot.difficulty == HARD
            else "PÍCARO"
            if snapshot.difficulty == PICARO
            else "INTERMEDIO"
        )
        state = STATE_LABELS.get(snapshot.runtime_state, "Sin partida")
        self.info.configure(text=f"Turno\n{turn}\n\nModo\n{difficulty}\n\nEstado\n{state}")
        self.symbol_legend.configure(
            text=(
                f"{snapshot.robot_symbol} · Robot\n"
                f"{snapshot.human_symbol} · Humano"
            )
        )
        clickable = snapshot.simulation and snapshot.runtime_state == RuntimeState.WAITING_HUMAN
        picaro_game = snapshot.difficulty == PICARO
        picaro_ready = clickable and snapshot.human_picaro_available
        if not picaro_ready:
            self._picaro_selecting = False
        if picaro_game:
            robot_resource = "Disponible" if snapshot.robot_picaro_available else "Usado"
            human_resource = "Disponible" if snapshot.human_picaro_available else "Usado"
            instruction = "\nSelecciona una ficha del robot" if self._picaro_selecting else ""
            action = f"\n{snapshot.action_status}" if snapshot.action_status else ""
            self.picaro_status.configure(
                text=f"Pícaro:\nRobot  {robot_resource}\nHumano {human_resource}{instruction}{action}"
            )
            self.picaro_button.configure(
                text="CANCELAR" if self._picaro_selecting else "USAR PÍCARO",
                state="normal" if picaro_ready else "disabled",
            )
            self.picaro_status.pack(fill="x", padx=24, pady=(12, 0))
            self.picaro_button.pack(anchor="w", padx=24, pady=(8, 0))
        else:
            self.picaro_status.pack_forget()
            self.picaro_button.pack_forget()
        for index, button in enumerate(self.cell_buttons):
            value = snapshot.board[index] or ""
            color = theme.X_COLOR if value == "X" else theme.O_COLOR if value == "O" else theme.BACKGROUND
            text_color = "#FFFFFF" if value == "X" else theme.TEXT_PRIMARY
            button.configure(
                text=value,
                state="normal" if (
                    self._picaro_selecting and clickable and value == snapshot.robot_symbol
                ) or (not self._picaro_selecting and clickable and not value) else "disabled",
                fg_color=color, text_color=text_color, text_color_disabled=text_color,
            )
        for name, value in {"Cámara": snapshot.camera_status, "Robot": snapshot.robot_status, "Tablero": snapshot.board_status}.items():
            dot, label = self.status_labels[name]
            color = self._status_color(value)
            dot.configure(text_color=color)
            label.configure(text=value, text_color=color)
        self.result_label.configure(text=RESULT_LABELS.get(snapshot.result, ""))
        self.error_label.configure(text=f"Error: {snapshot.last_error}" if snapshot.last_error else "")

    @staticmethod
    def _status_color(value: str) -> str:
        value = value.upper()
        if "ERROR" in value:
            return theme.ERROR
        if any(word in value for word in ("MOVIMIENTO", "ESPERANDO", "VERIFICANDO")):
            return theme.WARNING
        if "NO CONECT" in value or "NO DISPONIBLE" in value:
            return theme.DISABLED
        return theme.SUCCESS


def run_desktop_app(simulation: bool, config_path: Path | None = None) -> int:
    application = GameApplication(simulation=simulation, config=load_app_config(config_path))
    application.open()
    try:
        DesktopWindow(application).run()
    finally:
        application.close()
    return 0
