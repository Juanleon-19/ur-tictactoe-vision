"""Testable application service used by the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass

from ur_tictactoe.communication import STATUS_BUSY, STATUS_DONE, STATUS_READY
from ur_tictactoe.game import ACTIVE, HARD, HUMAN, INTERMEDIATE, GameSession
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState
from ur_tictactoe.vision.board_observer import CellState, PhysicalBoardState


@dataclass(frozen=True)
class AppConfig:
    robot_host: str = "192.168.1.10"
    robot_port: int = 502
    update_interval_ms: int = 100


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

    def __init__(self, simulation: bool, config: AppConfig | None = None) -> None:
        self.simulation = simulation
        self.config = config or AppConfig()
        self.session: GameSession | None = None
        self.runtime: PhysicalGameRuntime | None = None
        self._physical_occupied: set[int] = set()
        self._last_error: str | None = None

    def new_game(self, difficulty: str, human_first: bool) -> bool:
        if difficulty not in (HARD, INTERMEDIATE):
            raise ValueError(f"Unknown difficulty: {difficulty}")

        self.session = GameSession(difficulty, human_first, seed=None)
        self._physical_occupied = set()
        self._last_error = None
        if not self.simulation:
            self.runtime = None
            self._last_error = "REAL_MODE_NOT_CONFIGURED"
            return False

        self.runtime = PhysicalGameRuntime(self.session, SimulatedModbusClient())
        return self.runtime.start(self._physical_state())

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

    def update(self) -> None:
        """Advance at most one simulated transition for a Tkinter ``after`` tick."""
        if not self.simulation or self.runtime is None:
            return
        if self.runtime.state in (RuntimeState.WAITING_ROBOT, RuntimeState.ROBOT_BUSY):
            self.runtime.poll_robot()
        elif self.runtime.state == RuntimeState.VERIFYING_ROBOT:
            expected = self.session.pending_robot_move if self.session else None
            if expected is not None:
                self._physical_occupied.add(expected)
                self.runtime.update_board(self._physical_state())

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
                camera_status="SIMULADA" if self.simulation else "NO CONECTADA",
                robot_status="SIMULADO" if self.simulation else "NO CONECTADO",
                board_status="LISTO" if self.simulation else "NO DISPONIBLE",
                last_error=self._last_error,
                simulation=self.simulation,
            )

        runtime_snapshot = self.runtime.snapshot() if self.runtime else None
        return ApplicationSnapshot(
            board=self.session.board.cells,
            robot_symbol=self.session.robot,
            human_symbol=self.session.human,
            turn=self.session.turn,
            result=self.session.result,
            runtime_state=runtime_snapshot.state if runtime_snapshot else RuntimeState.ERROR,
            pending_robot_move=(
                runtime_snapshot.pending_robot_move if runtime_snapshot else None
            ),
            difficulty=self.session.difficulty,
            human_first=self.session.human == "X",
            camera_status="SIMULADA" if self.simulation else "NO CONECTADA",
            robot_status=self._robot_status(runtime_snapshot.state if runtime_snapshot else None),
            board_status="LISTO" if self.simulation else "NO DISPONIBLE",
            last_error=(runtime_snapshot.last_error if runtime_snapshot else self._last_error),
            simulation=self.simulation,
        )

    def _physical_state(self, occupied: set[int] | None = None) -> PhysicalBoardState:
        occupied = self._physical_occupied if occupied is None else occupied
        cells = {
            cell: CellState.OCCUPIED if cell in occupied else CellState.FREE
            for cell in range(1, 10)
        }
        return PhysicalBoardState(cells, {}, True, 3, 3, 1.0, {})

    def _robot_status(self, state: RuntimeState | None) -> str:
        if not self.simulation:
            return "NO CONECTADO"
        if state == RuntimeState.ROBOT_BUSY:
            return "EN MOVIMIENTO"
        if state == RuntimeState.VERIFYING_ROBOT:
            return "MOVIMIENTO TERMINADO"
        if state == RuntimeState.ERROR:
            return "ERROR"
        return "LISTO"
