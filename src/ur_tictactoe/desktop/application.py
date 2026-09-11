"""Testable application service used by the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Event, Lock, Thread, current_thread

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
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState, RuntimeSnapshot
from ur_tictactoe.communication.robot_recovery import BUSY_WARNING
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


@dataclass(frozen=True)
class CancelledGame:
    """Immutable evidence from a game retired by explicit recovery."""

    snapshot: RuntimeSnapshot
    command_sent: bool
    cause: str | None


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
        self.camera_busy = False
        self.camera_feedback = "Solo para esta sesión"
        self.detected_cameras: list[str] = []
        self._camera_worker: Thread | None = None
        self._robot_worker: Thread | None = None
        self.robot_busy = False
        self.robot_feedback = "Consulta de estado sin movimientos."
        self.cancelled_games: list[CancelledGame] = []
        self._game_notice: str | None = None
        self._closing = False
        self._shutdown_complete = Event()
        self._shutdown_worker: Thread | None = None
        self.shutdown_error: str | None = None
        self._restart_waiting_board = False
        self._lifecycle_lock = Lock()
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
                    dashboard_enabled=True,
                )
            except Exception as exc:
                self._last_error = f"CAMERA_CONFIG_ERROR: {exc}"

    def set_aruco_profile(self, profile: str) -> bool:
        """Session-only command, called on the same UI thread as update()."""
        self.profile_change_error = None
        if self.camera_busy or self.robot_busy or self._closing:
            self.profile_change_error = "Espere a que termine la operación de cámara."
            return False
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

    @property
    def physical_game_active(self) -> bool:
        return (not self.simulation and self.runtime is not None
                and self.runtime.state != RuntimeState.GAME_OVER)

    def _camera_operation(self, operation, message: str, success_message=None, *, clear_observation=True) -> bool:
        with self._lifecycle_lock:
            if self.physical_game_active or self.camera_busy or self.robot_busy or self._closing:
                self.camera_feedback = "Operación bloqueada: partida física activa u operación en curso."
                return False
            if self.simulation or self.real_backend is None:
                self.camera_feedback = "Cámara no disponible en este modo."
                return False
            self.camera_busy = True
        self.camera_feedback = message
        if clear_observation:
            self._last_observation = None

        def work():
            try:
                success = operation()
                if success is False:
                    self.camera_feedback = self.real_backend.last_error or "No se pudo completar la operación."
                else:
                    self.camera_feedback = (success_message() if success_message else
                                            "Cámara lista. Esperando estabilización del tablero.")
                self._last_error = self.real_backend.last_error
            except Exception as exc:
                self.camera_feedback = f"CAMERA_OPERATION_ERROR: {exc}"
            finally:
                with self._lifecycle_lock:
                    closing = self._closing
                    self.camera_busy = False
                if closing:
                    self.real_backend.close()

        with self._lifecycle_lock:
            if self._closing:
                self.camera_busy = False
                return False
            self._camera_worker = Thread(target=work, daemon=False, name="desktop-camera")
            self._camera_worker.start()
        return True

    def open_async(self) -> bool:
        return self._camera_operation(lambda: self.real_backend.open(), "Inicializando cámara...")

    @property
    def robot_query_allowed(self) -> bool:
        return (not self.simulation and self.real_backend is not None
                and not self.camera_busy and not self.robot_busy and not self._closing
                and (self.runtime is None or self.runtime.state in (RuntimeState.ERROR, RuntimeState.GAME_OVER)))

    def refresh_status(self) -> bool:
        return self._robot_operation("refresh_status")

    def reconnect_robot(self) -> bool:
        return self._robot_operation("reconnect_robot")

    @property
    def robot_recovery_allowed(self) -> bool:
        return (not self.simulation and self.real_backend is not None
                and not self.camera_busy and not self.robot_busy and not self._closing
                and (self.runtime is None or self.runtime.state in (RuntimeState.ERROR, RuntimeState.GAME_OVER)
                     or (self.runtime.state == RuntimeState.WAITING_HUMAN and not self.runtime.command_sent)))

    def recover_robot(self) -> bool:
        return self._robot_operation("recover_robot")

    @property
    def system_restart_allowed(self) -> bool:
        return not self._closing and not self.camera_busy and not self.robot_busy

    def restart_system(self) -> bool:
        if self.simulation:
            with self._lifecycle_lock:
                if not self.system_restart_allowed:
                    return False
                self._cancel_game_for_recovery()
                self.runtime = self.session = None
                self._physical_occupied.clear()
                self._last_error = None
                self.robot_feedback = "SISTEMA LISTO"
                return True
        return self._robot_operation("restart_system")

    def _cancel_game_for_recovery(self) -> None:
        if self.runtime is None:
            self.session = None
            return
        if self.runtime.state == RuntimeState.GAME_OVER:
            self.runtime.stop()
            self.runtime = self.session = None
            return
        self.cancelled_games.append(CancelledGame(
            self.runtime.snapshot(), self.runtime.command_sent,
            str(self.runtime.error_cause) if self.runtime.error_cause else None,
        ))
        # Only stop software progression/close its socket. No acknowledgement here.
        self.runtime.stop("PARTIDA_CANCELADA_POR_RECUPERACION")
        self.runtime = None
        self.session = None
        self._last_error = None  # The retired game's original error remains in history.
        self._game_notice = "PARTIDA CANCELADA · REQUIERE NUEVA PARTIDA"

    @staticmethod
    def _availability_error(error: str | None) -> bool:
        return bool(error and error.startswith((
            "MODBUS_", "ModbusConnectionError", "ModbusResponseError",
            "HARDWARE_NOT_AVAILABLE", "ROBOT_REQUIRES_RECOVERY",
        )))

    def _robot_operation(self, action: str) -> bool:
        restart = action == "restart_system"
        recovery = action in ("recover_robot", "restart_system")
        with self._lifecycle_lock:
            allowed = (self.system_restart_allowed and self.real_backend is not None if restart else
                       self.robot_recovery_allowed if recovery else self.robot_query_allowed)
            if not allowed:
                self.robot_feedback = (BUSY_WARNING if self.runtime and self.runtime.state == RuntimeState.ROBOT_BUSY
                                       else "Operación bloqueada: partida activa u operación en curso.")
                return False
            self.robot_busy = True
            if restart:
                self._restart_waiting_board = False
            if recovery:
                self._cancel_game_for_recovery()
        self.robot_feedback = "Reiniciando sistema..." if restart else "Recuperando robot mediante COMMAND0..." if recovery else "Consultando STATUS129..."

        def work():
            try:
                previous_error = self.real_backend.last_error
                recovered = getattr(self.real_backend, "recover_robot" if restart else action)()
                if restart and recovered and not self._closing:
                    self.real_backend.reset_board_observation()
                    self._restart_waiting_board = True
                self._last_observation = self.real_backend.last_observation
                if (self.real_backend.last_error or self._last_error == previous_error
                        or self._availability_error(self._last_error)):
                    self._last_error = self.real_backend.last_error
                self.robot_feedback = ("ROBOT RECUPERADO · READY" if recovery and recovered else
                                       self.real_backend.robot_error or "Estado actualizado. Sin escrituras ni movimientos.")
                if restart:
                    self.robot_feedback = ("Robot listo. Esperando estabilización del tablero." if recovered else
                                           "Robot en movimiento. Espere o use la parada física." if self.real_backend.controller_status == "BUSY" else
                                           "No se pudo conectar con el robot. Revise Ethernet y PolyScope." if self.real_backend.modbus_status == "ERROR" else
                                           "No se pudo reiniciar el robot. Revise PolyScope y el diagnóstico.")
                    if not recovered and self.real_backend.controller_status == "DESCONOCIDO":
                        self.robot_feedback = "No se conoce el estado del robot. Revise Ethernet, PolyScope y el diagnóstico."
                    if not recovered and "No se recibió READY" in (self.real_backend.robot_error or ""):
                        self.robot_feedback = "El robot no confirmó que estuviera listo a tiempo. Revise PolyScope."
                    if recovered and self.real_backend.camera_status != "CONECTADA":
                        self.robot_feedback = "Robot listo. Cámara no conectada: use RECONECTAR CÁMARA."
                if self._game_notice:
                    self.robot_feedback += "\n" + self._game_notice
                if self.runtime and self.runtime.state == RuntimeState.ERROR:
                    self.robot_feedback += " La partida sigue detenida; revisar su error y el estado físico."
            except Exception as exc:
                self.robot_feedback = f"ROBOT_DIAGNOSTIC_ERROR: {exc}"
            finally:
                with self._lifecycle_lock:
                    closing = self._closing
                    self.robot_busy = False
                if closing:
                    self.real_backend.close()

        with self._lifecycle_lock:
            if self._closing:
                self.robot_busy = False
                return False
            self._robot_worker = Thread(target=work, daemon=False, name="desktop-robot-diagnostic")
            self._robot_worker.start()
        return True

    def apply_camera(self, index: int, backend: str) -> bool:
        return self._camera_operation(
            lambda: self.real_backend.apply_camera(index, backend), "Inicializando cámara..."
        )

    def reconnect_camera(self) -> bool:
        return self._camera_operation(
            lambda: self.real_backend.reconnect_camera(), "Inicializando cámara..."
        )

    def detect_cameras(self, backend: str) -> bool:
        from ur_tictactoe.desktop.camera_controls import detect_local_cameras

        def detect():
            current = self.real_backend.camera_config
            # Never probe the capture we own, even when selecting another backend
            # or after a read failure (the local handle may still be alive).
            known = current.index if self.real_backend._camera_open else None
            self.detected_cameras = [f"Camera {i}" for i in detect_local_cameras(backend, known)]
            return True

        return self._camera_operation(
            detect, "Detectando cámaras...",
            lambda: ("Disponibles: " + ", ".join(self.detected_cameras)
                     if self.detected_cameras else "No se detectaron cámaras disponibles."),
            clear_observation=False,
        )

    def reset_board_observation(self) -> bool:
        if self.physical_game_active or self.camera_busy or self.robot_busy or self._closing:
            self.camera_feedback = "Operación bloqueada: partida física activa u operación en curso."
            return False
        if self.simulation or self.real_backend is None:
            self.camera_feedback = "Cámara no disponible en este modo."
            return False
        self.real_backend.reset_board_observation()
        self._last_observation = None
        self.camera_feedback = "Observación reiniciada. Esperando estabilización del tablero."
        return True

    def open(self) -> bool:
        """Open real resources; simulation has no external lifecycle."""
        if self.simulation:
            return True
        if self.real_backend is None or self.camera_busy or self.robot_busy or self._closing:
            return False
        opened = self.real_backend.open()
        self._last_error = self.real_backend.last_error
        return opened

    def close(self) -> None:
        self.shutdown_all()

    @property
    def shutdown_complete(self) -> bool:
        return (self._shutdown_complete.is_set()
                and not any(worker and worker.is_alive() for worker in
                            (self._camera_worker, self._robot_worker, self._shutdown_worker)))

    @property
    def shutdown_warning(self) -> str | None:
        if (self.runtime and (self.runtime.command_sent or self.runtime.state == RuntimeState.ROBOT_BUSY)
                or self.real_backend and getattr(self.real_backend, "controller_status", None) == "BUSY"):
            return "El robot puede seguir en movimiento. Cerrar la aplicación no lo detiene. Use la parada física si hay riesgo."
        return None

    def shutdown_all(self, *, wait=False) -> None:
        """Block actions, cancel locally, join workers and release resources.

        A native OpenCV open cannot be interrupted safely. The window waits in
        closing state until the driver returns and cleanup actually finishes.
        """
        with self._lifecycle_lock:
            if not self._closing:
                self._closing = True
                self._restart_waiting_board = False
                if self.runtime is not None:
                    self._cancel_game_for_recovery()
                self.robot_feedback = "Cerrando. Esperando liberación de dispositivos..."

                def cleanup():
                    try:
                        for worker in (self._camera_worker, self._robot_worker):
                            if worker is not None and worker is not current_thread():
                                worker.join()
                        if self.real_backend is not None:
                            self.real_backend.close()
                            error = self.real_backend.last_error
                            if error and "CLOSE_ERROR" in error:
                                self.shutdown_error = error
                    except Exception as exc:
                        self.shutdown_error = f"SHUTDOWN_ERROR: {exc}"
                    finally:
                        self._shutdown_complete.set()

                if any(worker and worker.is_alive() for worker in (self._camera_worker, self._robot_worker)):
                    self._shutdown_worker = Thread(target=cleanup, daemon=False, name="desktop-shutdown")
                    self._shutdown_worker.start()
                else:
                    cleanup()
        if wait:
            self._shutdown_complete.wait()
            if self._shutdown_worker is not None:
                self._shutdown_worker.join()

    def new_game(self, difficulty: str, human_first: bool, *, seed: int | None = None) -> bool:
        # Serialize authorization with recovery and the runtime's next transition.
        with self._lifecycle_lock:
            return self._new_game(difficulty, human_first, seed=seed)

    def _new_game(self, difficulty: str, human_first: bool, *, seed: int | None = None) -> bool:
        if not self.simulation and self.runtime and (
            self.runtime.command_sent or self.runtime.state in (
                RuntimeState.WAITING_ROBOT, RuntimeState.ROBOT_BUSY,
                RuntimeState.VERIFYING_ROBOT, RuntimeState.ACKNOWLEDGING_ROBOT,
            )
        ):
            self._last_error = "ROBOT_TURN_UNRESOLVED_CHECK_PHYSICAL_STATE"
            return False
        if self.camera_busy or self.robot_busy or self._closing:
            self._last_error = "CAMERA_INITIALIZING"
            return False
        if difficulty not in (HARD, INTERMEDIATE, PICARO):
            raise ValueError(f"Unknown difficulty: {difficulty}")

        if difficulty == PICARO and not self.simulation:
            self.session = None
            self.runtime = None
            self._last_error = "PICARO_SIMULATION_ONLY"
            return False

        if not self.simulation:
            if self.runtime and self.runtime.state == RuntimeState.ERROR:
                self._last_error = "ROBOT_REQUIRES_RECOVERY: partida detenida; pulse REINICIAR SISTEMA."
                return False
            backend = self.real_backend
            if backend is None or backend.camera_status != "CONECTADA":
                self._last_error = "CAMERA_NOT_CONNECTED"
                return False
            observation = self._last_observation
            if observation is None or not observation.ready:
                self._last_error = "BOARD_NOT_READY"
                return False
            if observation.uncertain_cells or observation.occupied_cells:
                self._last_error = "BOARD_UNCERTAIN" if observation.uncertain_cells else "BOARD_NOT_EMPTY"
                return False
            # Explicit start checks accessibility/READY afresh, read-only. Never reset.
            if not backend.refresh_status():
                self._last_error = backend.last_error or "HARDWARE_NOT_AVAILABLE"
                if backend.robot_status == "REQUIERE RECUPERACIÓN":
                    self._last_error = "ROBOT_REQUIRES_RECOVERY: Robot requiere recuperación. Pulse REINICIAR SISTEMA."
                return False

        self.session = GameSession(difficulty, human_first, seed=seed)
        self._physical_occupied = set()
        self._last_error = None
        self._action_status = None
        self._action_status_ticks = 0
        self._game_notice = None
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
            self.session, self.real_backend.modbus_client, manage_connection=True
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
        if self._closing:
            return
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
        if self.real_backend is None or self.camera_busy or self.robot_busy or self._closing:
            return
        observation = self.real_backend.tick()
        self._last_observation = observation
        if self.real_backend.last_error:
            self._last_error = self.real_backend.last_error
        if self.real_backend.camera_status == "ERROR":
            if self._restart_waiting_board:
                self.robot_feedback = "No se recibe imagen. Use RECONECTAR CÁMARA."
            if self.runtime and self.runtime.state not in (RuntimeState.ERROR, RuntimeState.GAME_OVER):
                self.runtime.stop("CAMERA_ERROR")
            return
        with self._lifecycle_lock:
            if not self.robot_busy and not self._closing:
                self._advance_real_runtime(observation)

    def _advance_real_runtime(self, observation) -> None:
        if self._restart_waiting_board:
            if self.real_backend.camera_status != "CONECTADA":
                self.robot_feedback = "Cámara no conectada. Use RECONECTAR CÁMARA."
            elif observation and observation.ready and not observation.uncertain_cells:
                if observation.occupied_cells:
                    self.robot_feedback = "Retire las fichas del tablero para iniciar otra partida."
                elif self.real_backend.robot_status == "LISTO":
                    self.robot_feedback = "SISTEMA LISTO"
                    self._last_error = self.real_backend.last_error
                    self._restart_waiting_board = False
        if self.runtime is None or observation is None:
            return
        if self.runtime.state in (RuntimeState.ERROR, RuntimeState.GAME_OVER):
            return
        if self.runtime.state in (
            RuntimeState.WAITING_ROBOT,
            RuntimeState.ROBOT_BUSY,
            RuntimeState.ACKNOWLEDGING_ROBOT,
        ):
            status = self.runtime.poll_robot()
            record_status = getattr(self.real_backend, "record_robot_status", None)
            if record_status is not None:
                record_status(status, self.runtime.error_cause)
        elif self.runtime.state in (
            RuntimeState.WAITING_HUMAN,
            RuntimeState.VERIFYING_ROBOT,
        ):
            self.runtime.update_board(observation)

    def diagnostic_snapshot(self) -> DiagnosticSnapshot:
        if self.simulation or self.real_backend is None:
            return DiagnosticSnapshot(profile=self._session_profile)
        history = tuple(
            f"PARTIDA CANCELADA · REQUIERE NUEVA PARTIDA\n"
            f"Estado anterior: {entry.snapshot.state.value}; error: {entry.snapshot.last_error}\n"
            f"COMMAND posiblemente entregado: {entry.command_sent}; pending_robot_move: {entry.snapshot.pending_robot_move}\n"
            f"Tablero lógico: {entry.snapshot.board}; causa: {entry.cause or '—'}"
            for entry in self.cancelled_games
        )
        return replace(self.real_backend.diagnostic_snapshot(), game_history=history)

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
                action_status=self._game_notice,
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
        if state == RuntimeState.ACKNOWLEDGING_ROBOT:
            return "ESPERANDO READY"
        if state == RuntimeState.ERROR:
            return "ERROR" if self.simulation else "REQUIERE RECUPERACIÓN"
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
