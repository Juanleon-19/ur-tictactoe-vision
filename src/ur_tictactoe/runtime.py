"""Application orchestration for one physically observed game."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from time import monotonic

from ur_tictactoe.communication import (
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    ModbusConnectionError,
    ModbusResponseError,
)
from ur_tictactoe.game import HUMAN, PICARO_ACTION, ROBOT, GameSession
from ur_tictactoe.vision.board_observer import PhysicalBoardState


class RuntimeState(str, Enum):
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_ROBOT = "WAITING_ROBOT"
    ROBOT_BUSY = "ROBOT_BUSY"
    VERIFYING_ROBOT = "VERIFYING_ROBOT"
    ACKNOWLEDGING_ROBOT = "ACKNOWLEDGING_ROBOT"
    GAME_OVER = "GAME_OVER"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RuntimeSnapshot:
    state: RuntimeState
    turn: str | None
    result: str
    board: tuple[str | None, ...]
    pending_robot_move: int | None
    last_error: str | None


class PhysicalGameRuntime:
    """Coordinate stable board states, a game session, and Modbus polling."""

    def __init__(self, session: GameSession, modbus_client: object, *,
                 manage_connection=False, timeout=60.0, clock=monotonic) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        self.manage_connection = manage_connection
        self.timeout, self.clock = timeout, clock
        self._connected = False
        self._deadline = None
        self._saw_busy = False
        self.session = session
        self.modbus_client = modbus_client
        self.state = self._turn_state()
        self.command_sent = False
        self.last_error: str | None = None
        self.error_cause: Exception | None = None
        self._started = False

    def start(self, physical_state: PhysicalBoardState) -> bool:
        """Accept a game only when the stable physical board is empty."""
        if physical_state.occupied_cells:
            return self._reject_start("BOARD_NOT_EMPTY")
        if not physical_state.ready:
            return self._reject_start("BOARD_NOT_READY")
        if physical_state.uncertain_cells:
            return self._reject_start("BOARD_UNCERTAIN")

        self._started = True
        self.last_error = None
        self.error_cause = None
        self.state = self._turn_state()
        return True

    def update_board(self, physical_state: PhysicalBoardState) -> int | None:
        """Process one stable observation when the current state permits it."""
        if not self._started or not self._check_deadline() or self.state in (
            RuntimeState.ERROR,
            RuntimeState.GAME_OVER,
            RuntimeState.ROBOT_BUSY,
            RuntimeState.WAITING_ROBOT,
            RuntimeState.ACKNOWLEDGING_ROBOT,
        ):
            return None

        if self.state == RuntimeState.VERIFYING_ROBOT:
            self._verify_robot_move(physical_state)
            return None

        if self.state != RuntimeState.WAITING_HUMAN or self.session.turn != HUMAN:
            return None
        if not physical_state.ready:
            self.last_error = "BOARD_NOT_READY"
            return None
        if physical_state.uncertain_cells:
            self.last_error = "BOARD_UNCERTAIN"
            return None

        logical = self._logical_occupied()
        added = physical_state.occupied_cells - logical
        removed = logical - physical_state.occupied_cells
        if not added and not removed:
            self.last_error = None
            return None
        if len(added) != 1 or removed:
            self.last_error = self._change_reason(added, removed)
            return None

        cell = next(iter(added))
        self.session.play_human_move(cell)
        self.last_error = None
        self.state = (
            RuntimeState.GAME_OVER if not self.session.is_active else RuntimeState.WAITING_ROBOT
        )
        return cell

    def poll_robot(self) -> int | None:
        """Advance the Modbus handshake by one status read without blocking."""
        if not self._started or not self._check_deadline() or self.state in (
            RuntimeState.ERROR,
            RuntimeState.GAME_OVER,
            RuntimeState.VERIFYING_ROBOT,
        ):
            return None
        if self.state == RuntimeState.ACKNOWLEDGING_ROBOT:
            try:
                status = self.modbus_client.read_status()
                if status == STATUS_READY:
                    self._close_connection()
                    self._deadline = None
                    self.state = self._turn_state()
                elif status != STATUS_DONE:
                    self._handle_robot_error("UNEXPECTED_ACK_STATUS")
                return status
            except (ModbusConnectionError, ModbusResponseError) as exc:
                self._handle_robot_error(type(exc).__name__, exc)
                return None
        if self.session.turn != ROBOT:
            return None

        try:
            if self.manage_connection and not self._connected:
                self._connected = True  # Cleanup even if connect raises.
                self.modbus_client.connect()
                self._deadline = self.clock() + self.timeout
                self._saw_busy = False
            if self.session.pending_robot_move is None:
                self.session.request_robot_move()
            self.state = RuntimeState.WAITING_ROBOT
            status = self.modbus_client.read_status()
            if status == STATUS_READY:
                if self.manage_connection and self._saw_busy:
                    self._handle_robot_error("UNEXPECTED_READY_AFTER_BUSY")
                    return status
                if not self.command_sent:
                    self.command_sent = True  # Delivery may succeed even if the reply is lost.
                    self.modbus_client.write_command(self.session.pending_robot_move)
            elif status == STATUS_BUSY:
                if self.manage_connection and not self.command_sent:
                    self._handle_robot_error("UNEXPECTED_BUSY_BEFORE_COMMAND")
                    return status
                self._saw_busy = True
                self.state = RuntimeState.ROBOT_BUSY
            elif status == STATUS_DONE:
                if self.manage_connection and (not self.command_sent or not self._saw_busy):
                    self._handle_robot_error("UNEXPECTED_DONE_BEFORE_BUSY")
                    return status
                if self.manage_connection:
                    self._deadline = self.clock() + self.timeout
                self.state = RuntimeState.VERIFYING_ROBOT
                self.last_error = "ROBOT_MOVE_AWAITING_PHYSICAL_VERIFICATION"
            elif status == STATUS_ERROR:
                self._handle_robot_error("MODBUS_STATUS_ERROR")
            return status
        except (ModbusConnectionError, ModbusResponseError) as exc:
            self._handle_robot_error(type(exc).__name__, exc)
            return None

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            state=self.state,
            turn=self.session.turn,
            result=self.session.result,
            board=self.session.board.cells,
            pending_robot_move=self.session.pending_robot_move,
            last_error=self.last_error,
        )

    def confirm_simulated_robot_replacement(self) -> None:
        """Confirm a Pícaro replacement without pretending occupancy can verify it."""
        decision = self.session.pending_robot_decision
        if self.state != RuntimeState.VERIFYING_ROBOT or decision is None:
            raise ValueError("There is no robot replacement awaiting verification")
        if decision.action != PICARO_ACTION:
            raise ValueError("The pending robot decision is not a Pícaro replacement")
        try:
            self.session.confirm_robot_move()
            self.modbus_client.clear_command()
        except (ModbusConnectionError, ModbusResponseError) as exc:
            self._handle_robot_error(type(exc).__name__, exc)
            return
        self.command_sent = False
        self.last_error = None
        self.state = (
            RuntimeState.GAME_OVER
            if not self.session.is_active
            else RuntimeState.WAITING_HUMAN
        )

    def confirm_simulated_human_replacement(self, cell: int) -> None:
        """Apply a simulated owner change without weakening occupancy checks."""
        if not self._started or self.state != RuntimeState.WAITING_HUMAN:
            raise ValueError("The runtime is not waiting for a simulated human action")
        self.session.play_human_picaro(cell)
        self.last_error = None
        self.state = (
            RuntimeState.GAME_OVER
            if not self.session.is_active
            else RuntimeState.WAITING_ROBOT
        )

    def _verify_robot_move(self, physical_state: PhysicalBoardState) -> None:
        if not physical_state.ready:
            self.last_error = "BOARD_NOT_READY"
            return
        if physical_state.uncertain_cells:
            self.last_error = "BOARD_UNCERTAIN"
            return
        expected_cell = self.session.pending_robot_move
        if expected_cell is None:
            self._handle_robot_error("NO_PENDING_ROBOT_MOVE")
            return
        expected = self._logical_occupied() | {expected_cell}
        if physical_state.occupied_cells != expected:
            missing = expected - physical_state.occupied_cells
            unexpected = physical_state.occupied_cells - expected
            self.last_error = self._change_reason(unexpected, missing)
            return

        try:
            self.session.confirm_robot_move()
            self.modbus_client.clear_command()
        except (ModbusConnectionError, ModbusResponseError) as exc:
            self._handle_robot_error(type(exc).__name__, exc)
            return
        self.command_sent = False
        self.last_error = None
        self.state = (
            RuntimeState.ACKNOWLEDGING_ROBOT if self.manage_connection else
            RuntimeState.GAME_OVER if not self.session.is_active else RuntimeState.WAITING_HUMAN
        )
        if self.manage_connection:
            self._deadline = self.clock() + self.timeout

    def _handle_robot_error(self, reason: str, cause: Exception | None = None) -> None:
        # Never acknowledge/reset an uncertain command or discard its evidence.
        if not self.manage_connection and self.session.pending_robot_move is not None:
            self.session.cancel_robot_move()
        self.state = RuntimeState.ERROR
        self.last_error = reason
        self.error_cause = cause
        self._deadline = None
        try:
            self._close_connection()
        except (ModbusConnectionError, ModbusResponseError) as exc:
            self.error_cause = cause or exc
            self.last_error += "; CLOSE_FAILED"

    def stop(self, reason="OPERATOR_ABORT", cause=None):
        """Stop software progression; no robot commands and no physical stop."""
        self._handle_robot_error(reason, cause)

    def _close_connection(self):
        if self.manage_connection and self._connected:
            self._connected = False
            self.modbus_client.close()

    def _check_deadline(self):
        if self._deadline is not None and self.clock() >= self._deadline:
            self._handle_robot_error("ROBOT_TIMEOUT", TimeoutError("Robot stage timed out"))
            return False
        return True

    def _reject_start(self, reason: str) -> bool:
        self.state = RuntimeState.ERROR
        self.last_error = reason
        return False

    def _logical_occupied(self) -> frozenset[int]:
        return frozenset(
            cell for cell in range(1, 10) if self.session.board.cell(cell) is not None
        )

    def _turn_state(self) -> RuntimeState:
        if not self.session.is_active:
            return RuntimeState.GAME_OVER
        return (
            RuntimeState.WAITING_HUMAN
            if self.session.turn == HUMAN
            else RuntimeState.WAITING_ROBOT
        )

    @staticmethod
    def _change_reason(added: set[int] | frozenset[int], removed: set[int] | frozenset[int]) -> str:
        return f"INCONSISTENT_BOARD_CHANGE added={sorted(added)} removed={sorted(removed)}"
