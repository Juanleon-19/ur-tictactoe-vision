"""Testable application service used by the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass

from ur_tictactoe.communication import STATUS_BUSY, STATUS_DONE, STATUS_READY
from ur_tictactoe.config import load_vision_config
from ur_tictactoe.desktop.real_backend import RealGameBackend
from ur_tictactoe.desktop.diagnostics import DiagnosticSnapshot
from ur_tictactoe.desktop.settings import AppConfig
from ur_tictactoe.game import (
    ACTIVE,
    HARD,
    HUMAN,
    INTERMEDIATE,
    PICARO,
    PICARO_ACTION,
    GameSession,
)
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState
from ur_tictactoe.vision.aruco import ARUCO_PROFILES
from ur_tictactoe.vision.board_observer import CellState, PhysicalBoardState


@dataclass(frozen=True)
class ApplicationSnapshot:
    board: tuple[str | None, ...]
    robot_symbol: str | None
    human_symbol: str | None
    turn: str | None
    result: str
    runtime_state: RuntimeState | None
    pending_robot_move: int | None
    difficulty: str | None
    human_first: bool | None
    camera_status: str
    robot_status: str
    board_status: str
    last_error: str | None
    simulation: bool
    robot_picaro_available: bool
    human_picaro_available: bool
    action_status: str | None


class SimulatedModbusClient:
    """Minimal deterministic READY/BUSY/DONE transport for the runtime."""

    def __init__(self) -> None:
        self._statuses = [STATUS_READY]
        self.commands: list[int] = []

    def read_status(self) -> int:
        if not self._statuses:
            return STATUS_READY
        return self._statuses.pop(0)

    def write_command(self, cell: int) -> None:
        self.commands.append(cell)
        self._statuses.extend((STATUS_BUSY, STATUS_DONE))

    def clear_command(self) -> None:
        self.commands.append(0)


class GameApplication:
    """Own one game and expose UI-safe commands and snapshots."""

    def __init__(
        self,
        simulation: bool,
        config: AppConfig | None = None,
        real_backend: RealGameBackend | None = None,
    ) -> None:
        self.simulation = simulation
        self.config = config or AppConfig()
        self._session_profile = self.config.aruco_profile
        self.profile_change_error: str | None = None
        self.session: GameSession | None = None
        self.runtime: PhysicalGameRuntime | None = None
        self._physical_occupied: set[int] = set()
        self._last_error: str | None = None
        self._action_status: str | None = None
        self._action_status_ticks = 0
        self.real_backend = real_backend
        self._last_observation: PhysicalBoardState | None = None
        if not simulation and real_backend is None:
            try:
                vision_config = load_vision_config(self.config.vision_config_path)
                self.real_backend = RealGameBackend(
                    vision_config,
                    self.config.robot_host,
                    self.config.robot_port,
                    self.config.aruco_profile,
                )
            except Exception as exc:
                self._last_error = f"CAMERA_CONFIG_ERROR: {exc}"

    def set_aruco_profile(self, profile: str) -> bool:
        """Session-only command, called on the same UI thread as update()."""
        self.profile_change_error = None
        if not self.simulation and self.runtime is not None and (
            self.runtime.state != RuntimeState.GAME_OVER
        ):
            self.profile_change_error = "No se puede cambiar el perfil durante una partida activa."
            return False
        if profile not in ARUCO_PROFILES:
            self.profile_change_error = "Perfil de visión no válido."
            return False
        if not self.simulation:
            if self.real_backend is None:
                self.profile_change_error = "Visión no disponible."
                return False
            try:
                self.real_backend.set_aruco_profile(profile)
            except Exception:
                self.profile_change_error = "No se pudo aplicar el perfil de visión."
                return False
            self._last_observation = None
        self._session_profile = profile
        return True

    def open(self) -> bool:
        """Open real resources; simulation has no external lifecycle."""
        if self.simulation:
            return True
        if self.real_backend is None:
            return False
        opened = self.real_backend.open()
        self._last_error = self.real_backend.last_error
        return opened

    def close(self) -> None:
        if self.real_backend is not None:
            self.real_backend.close()

    def new_game(self, difficulty: str, human_first: bool, *, seed: int | None = None) -> bool:
        if difficulty not in (HARD, INTERMEDIATE, PICARO):
            raise ValueError(f"Unknown difficulty: {difficulty}")

        if difficulty == PICARO and not self.simulation:
            self.session = None
            self.runtime = None
            self._last_error = "PICARO_SIMULATION_ONLY"
            return False

        self.session = GameSession(difficulty, human_first, seed=seed)
        self._physical_occupied = set()
        self._last_error = None
        self._action_status = None
        self._action_status_ticks = 0
        if self.simulation:
            self.runtime = PhysicalGameRuntime(self.session, SimulatedModbusClient())
            return self.runtime.start(self._physical_state())

        if self.real_backend is None or not self.real_backend.is_open:
            self.runtime = None
            self._last_error = (
                self.real_backend.last_error or "HARDWARE_NOT_AVAILABLE"
                if self.real_backend is not None
                else self._last_error or "HARDWARE_NOT_AVAILABLE"
            )
            return False
        if self._last_observation is None:
            self.runtime = None
            self._last_error = "BOARD_NOT_READY"
            return False

        self.runtime = PhysicalGameRuntime(
            self.session, self.real_backend.modbus_client
        )
        started = self.runtime.start(self._last_observation)
        self._last_error = self.runtime.last_error
        return started

    def play_human_cell(self, cell: int) -> bool:
        if not self.simulation or self.runtime is None or self.session is None:
            return False
        if self.runtime.state != RuntimeState.WAITING_HUMAN:
            return False
        if cell not in self.session.board.available_moves():
            return False

        observed = self._physical_occupied | {cell}
        move = self.runtime.update_board(self._physical_state(observed))
        if move is None:
            return False
        self._physical_occupied = observed
        return True

    def play_human_picaro(self, cell: int) -> bool:
        """Apply the human replacement through the simulation-only runtime path."""
        if not self.simulation or self.runtime is None or self.session is None:
            return False
        if self.runtime.state != RuntimeState.WAITING_HUMAN:
            return False
        try:
            self.runtime.confirm_simulated_human_replacement(cell)
        except ValueError:
            return False
        self._action_status = f"Humano usa Pícaro · Celda {cell}"
        self._action_status_ticks = 20
        return True

    def update(self) -> None:
        """Advance at most one simulated transition for a Tkinter ``after`` tick."""
        if self._action_status_ticks > 0:
            self._action_status_ticks -= 1
            if self._action_status_ticks == 0:
                self._action_status = None
        if not self.simulation:
            self._update_real()
            return
        if self.runtime is None:
            return
        if self.runtime.state in (RuntimeState.WAITING_ROBOT, RuntimeState.ROBOT_BUSY):
            self.runtime.poll_robot()
        elif self.runtime.state == RuntimeState.VERIFYING_ROBOT:
            expected = self.session.pending_robot_move if self.session else None
            if expected is not None:
                decision = self.session.pending_robot_decision
                if decision is not None and decision.action == PICARO_ACTION:
                    self.runtime.confirm_simulated_robot_replacement()
                    self._action_status = f"Robot usa Pícaro · Celda {expected}"
                    self._action_status_ticks = 20
                else:
                    self._physical_occupied.add(expected)
                    self.runtime.update_board(self._physical_state())

    def _update_real(self) -> None:
        if self.real_backend is None:
            return
        observation = self.real_backend.tick()
        if observation is not None:
            self._last_observation = observation
        if self.real_backend.last_error:
            self._last_error = self.real_backend.last_error
        if self.real_backend.camera_status == "ERROR":
            return
        if self.runtime is None or observation is None:
            return
        if self.runtime.state in (RuntimeState.ERROR, RuntimeState.GAME_OVER):
            return
        if self.runtime.state in (
            RuntimeState.WAITING_ROBOT,
            RuntimeState.ROBOT_BUSY,
        ):
            self.runtime.poll_robot()
        elif self.runtime.state in (
            RuntimeState.WAITING_HUMAN,
            RuntimeState.VERIFYING_ROBOT,
        ):
            self.runtime.update_board(observation)

    def diagnostic_snapshot(self) -> DiagnosticSnapshot:
        if self.simulation or self.real_backend is None:
            return DiagnosticSnapshot(profile=self._session_profile)
        return self.real_backend.diagnostic_snapshot()

    def snapshot(self) -> ApplicationSnapshot:
        if self.session is None:
            return ApplicationSnapshot(
                board=(None,) * 9,
                robot_symbol=None,
                human_symbol=None,
                turn=None,
                result=ACTIVE,
                runtime_state=None,
                pending_robot_move=None,
                difficulty=None,
                human_first=None,
                camera_status=(
                    "SIMULADA"
                    if self.simulation
                    else self.real_backend.camera_status
                    if self.real_backend
                    else "ERROR"
                ),
                robot_status=(
                    "SIMULADO" if self.simulation else self._robot_status(None)
                ),
                board_status="LISTO" if self.simulation else self._board_status(),
                last_error=self._last_error,
                simulation=self.simulation,
                robot_picaro_available=False,
                human_picaro_available=False,
                action_status=None,
            )

        runtime_snapshot = self.runtime.snapshot() if self.runtime else None
        return ApplicationSnapshot(
            board=self.session.board.cells,
            robot_symbol=self.session.robot,
            human_symbol=self.session.human,
            turn=self.session.turn,
            result=self.session.result,
            runtime_state=runtime_snapshot.state if runtime_snapshot else None,
            pending_robot_move=(
                runtime_snapshot.pending_robot_move if runtime_snapshot else None
            ),
            difficulty=self.session.difficulty,
            human_first=self.session.human == "X",
            camera_status=(
                "SIMULADA"
                if self.simulation
                else self.real_backend.camera_status
                if self.real_backend
                else "ERROR"
            ),
            robot_status=self._robot_status(runtime_snapshot.state if runtime_snapshot else None),
            board_status="LISTO" if self.simulation else self._board_status(),
            last_error=(
                runtime_snapshot.last_error
                if runtime_snapshot and runtime_snapshot.last_error
                else self._last_error
            ),
            simulation=self.simulation,
            robot_picaro_available=self.session.robot_picaro_available,
            human_picaro_available=self.session.human_picaro_available,
            action_status=self._action_status,
        )

    def _physical_state(self, occupied: set[int] | None = None) -> PhysicalBoardState:
        occupied = self._physical_occupied if occupied is None else occupied
        cells = {
            cell: CellState.OCCUPIED if cell in occupied else CellState.FREE
            for cell in range(1, 10)
        }
        return PhysicalBoardState(cells, {}, True, 3, {})

    def _robot_status(self, state: RuntimeState | None) -> str:
        if not self.simulation:
            if self.real_backend is None:
                return "NO CONECTADO"
            if self.real_backend.robot_status != "LISTO":
                return self.real_backend.robot_status
        if state == RuntimeState.ROBOT_BUSY:
            return "EN MOVIMIENTO"
        if state == RuntimeState.VERIFYING_ROBOT:
            return "MOVIMIENTO TERMINADO"
        if state == RuntimeState.ERROR:
            return "ERROR"
        return "LISTO"

    def _board_status(self) -> str:
        observation = self._last_observation
        if observation is None:
            return "ESPERANDO TABLERO"
        if not observation.ready:
            return "NO LISTO"
        if observation.uncertain_cells:
            return "INCIERTO"
        return "LISTO"
