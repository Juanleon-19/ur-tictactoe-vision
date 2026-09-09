"""Scrollable operator help with read-only evidence and informational navigation."""

import customtkinter as ctk

from ur_tictactoe.desktop.commissioning_status import (
    latest_commissioning, validation_history, next_operational_step,
)
from ur_tictactoe.desktop.help_content import SECTIONS, SAFETY, BOARD_MAP, help_text
from ur_tictactoe.desktop.operator_guidance import (
    STEP_TITLES, HISTORY_NOTICE, PROBLEMS, procedure, problem_guidance,
)
from ur_tictactoe.desktop.operator_style import card, label, badge, paragraph, status_color, PROFILE_LABELS, theme
from ur_tictactoe.desktop.settings import application_directory


class HelpPanel(ctk.CTkFrame):
    def __init__(self, parent, application):
        super().__init__(parent, fg_color="transparent")
        self.application = application
        self.pack(fill="both", expand=True, padx=12, pady=6)
        general_card = card(self, "ESTADO GENERAL")
        general_card.pack(fill="x", pady=(0, 8))
        self.general = general_card.winfo_children()[0]
        row = ctk.CTkFrame(general_card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 10))
        row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="states")
        self.status_labels = {}
        for col, name in enumerate(("Cámara", "Tablero", "Robot", "Perfil")):
            item = ctk.CTkFrame(row, fg_color="transparent")
            item.grid(row=0, column=col, sticky="ew", padx=(0, 8))
            label(item, name, color=theme.TEXT_SECONDARY).pack(anchor="w")
            self.status_labels[name] = badge(item, "—")
            self.status_labels[name].pack(fill="x")
        self.section = ctk.CTkOptionMenu(self, values=list(SECTIONS), width=235,
                                        command=lambda _: self.select_section())
        self.section.pack(anchor="w", pady=(0, 8))
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.report = None
        self.history = {}
        self.selected_procedure = None
        self.selected_problem = PROBLEMS[0]
        self._key = None
        self.reload_report()

    def reload_report(self):
        directory = application_directory() / "reports"
        self.report = latest_commissioning(directory)
        self.history = validation_history(directory)
        self._key = None
        self.refresh()

    def select_section(self):
        self.selected_procedure = None
        self._key = None
        self.refresh()
        self.content._parent_canvas.yview_moveto(0)

    def show_procedure(self, step):
        self.selected_procedure = step
        self._key = None
        self.refresh()
        self.content._parent_canvas.yview_moveto(0)

    def show_problem(self, problem):
        self.selected_problem = problem
        self._key = None
        self.refresh()

    def _card(self, title, text=None):
        item = card(self.content, title)
        item.pack(fill="x", pady=(0, 8))
        if text:
            paragraph(item, text)
        return item

    def _button(self, parent, text, command):
        button = ctk.CTkButton(parent, text=text, command=command, height=30,
                               fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                               font=ctk.CTkFont("Segoe UI", 11, "bold"))
        button.pack(anchor="w", padx=14, pady=(2, 10))
        return button

    def _evidence(self, parent, step, report):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(4, 0))
        label(row, f"{step}  {STEP_TITLES[step]}", bold=True).pack(side="left")
        status = report.results[step] if report else "PENDIENTE"
        badge(row, status).pack(side="right")
        if report:
            paragraph(parent, f"{report.timestamp} · SHA: {report.software_commit_sha}\n{report.source}")

    def refresh(self):
        snapshot = self.application.snapshot()
        diagnostic = self.application.diagnostic_snapshot()
        for name, value in (("Cámara", snapshot.camera_status), ("Tablero", snapshot.board_status),
                            ("Robot", snapshot.robot_status), ("Perfil", PROFILE_LABELS[diagnostic.profile])):
            self.status_labels[name].configure(text=value, text_color=status_color(value))
        live = ((snapshot.camera_status, snapshot.board_status, snapshot.robot_status,
                 diagnostic.visible_ids, diagnostic.illumination, diagnostic.profile)
                if self.section.get() == "Solucionar problema" else None)
        key = (self.section.get(), self.selected_procedure, self.selected_problem, live)
        if key == self._key:
            return
        self._key = key
        for child in self.content.winfo_children():
            child.destroy()
        if self.selected_procedure:
            step = self.selected_procedure
            panel = self._card(f"{step} — {STEP_TITLES[step].upper()}")
            badge(panel, procedure(step)["Nivel de riesgo"]).pack(anchor="w", padx=14, pady=4)
            self._button(panel, "VOLVER", self.select_section)
            for title, text in procedure(step).items():
                self._card(title.upper(), text)
            self._card("CONSULTA ÚNICAMENTE", "Ejecutar desde harness de commissioning. "
                       "Este panel no ejecuta acciones.\n\n" + SAFETY)
            return
        section = self.section.get()
        if section == "Puesta en marcha":
            step = next_operational_step(self.history)
            panel = self._card("SIGUIENTE PASO RECOMENDADO")
            if step:
                paragraph(panel, f"{step} — {STEP_TITLES[step].upper()}\n" + (
                          "Comprueba que una oclusión temporal con la mano no produzca "
                          "una ocupación falsa persistente." if step == "C5" else procedure(step)["Objetivo"]))
                self.procedure_button = self._button(panel, "VER PROCEDIMIENTO", lambda step=step: self.show_procedure(step))
            else:
                paragraph(panel, "Secuencia con evidencia PASS. Verifique el estado actual del hardware.")
            panel = self._card("HISTORIAL DE VALIDACIÓN FÍSICA", HISTORY_NOTICE)
            if not self.history:
                paragraph(panel, "Sin resultados de commissioning disponibles.")
            for step in STEP_TITLES:
                self._evidence(panel, step, self.history.get(step))
        elif section == "Commissioning":
            panel = self._card("ÚLTIMA SESIÓN", HISTORY_NOTICE)
            if self.report:
                paragraph(panel, f"{self.report.source}\n{self.report.timestamp}\nSHA: {self.report.software_commit_sha}")
                for step in sorted(self.report.results, key=lambda s: int(s[1:])):
                    self._evidence(panel, step, self.report)
            else:
                paragraph(panel, "Sin resultados de commissioning disponibles.")
            panel = self._card("PROCEDIMIENTOS", "Consulta offline. Ejecutar desde harness de commissioning.")
            paragraph(panel, "C0 — Software: dependencias, configuración y evidencia pytest.")
            self.procedure_selector = ctk.CTkOptionMenu(panel, values=[f"C{i}" for i in range(1, 15)],
                                                       command=self.show_procedure)
            self.procedure_selector.pack(anchor="w", padx=14, pady=(2, 12))
            for step in STEP_TITLES:
                if step != "C0":
                    self._card(f"{step} — {STEP_TITLES[step]}", procedure(step)["Nivel de riesgo"])
        elif section == "Solucionar problema":
            panel = self._card("SOLUCIONAR PROBLEMA")
            self.problem_selector = ctk.CTkOptionMenu(panel, values=list(PROBLEMS),
                                                     command=self.show_problem, width=260)
            self.problem_selector.set(self.selected_problem)
            self.problem_selector.pack(anchor="w", padx=14, pady=(2, 10))
            diagnosis, advice = problem_guidance(self.selected_problem, snapshot, diagnostic)
            self._card(self.selected_problem.upper(), diagnosis)
            self._card("PASOS RECOMENDADOS", advice)
            if snapshot.simulation:
                self._card("SIMULACIÓN", "Los estados simulados no acreditan validación física.")
        else:
            text = help_text(section, snapshot, self.report)
            # Render the cell mapping geometrically, not with spacing-dependent text.
            text = text.replace(BOARD_MAP, "{BOARD_MAP}")
            for index, part in enumerate(text.split("\n\n")):
                if part == "{BOARD_MAP}":
                    panel = self._card("MAPA DEL TABLERO")
                    grid = ctk.CTkFrame(panel, fg_color="transparent")
                    grid.pack(fill="x", padx=14, pady=(0, 10))
                    grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="cells")
                    for cell in range(1, 10):
                        tile = badge(grid, f"CELL{cell}\nID{cell + 9}")
                        tile.configure(text_color=theme.PRIMARY, height=40)
                        tile.grid(row=(cell-1)//3, column=(cell-1)%3, sticky="ew", padx=3, pady=3)
                else:
                    self._card(section.upper() if index == 0 else "REFERENCIA", part)
