"""Guided physical acceptance using the productive observer, game and runtime."""

from ur_tictactoe.game import GameSession
from ur_tictactoe.runtime import PhysicalGameRuntime, RuntimeState


class RecordedClient:
    def __init__(self, runner, client):
        self.runner, self.client = runner, client
        self.events = runner.current_observed.setdefault("modbus_events", [])

    def connect(self):
        with self.runner.stage("modbus_connect"):
            self.client.connect()
        self.events.append({"event": "connected", "timestamp": self.runner.clock()})

    def read_status(self):
        with self.runner.stage("modbus_read"):
            status = self.client.read_status()
        self.events.append({"status": status, "timestamp": self.runner.clock()})
        return status

    def write_command(self, cell):
        self.events.append({"command": cell, "attempted": True, "timestamp": self.runner.clock()})
        with self.runner.stage("modbus_write"):
            self.client.write_command(cell)

    def clear_command(self):
        self.write_command(0)

    def close(self):
        with self.runner.stage("modbus_close"):
            self.client.close()
        self.events.append({"event": "closed", "timestamp": self.runner.clock()})


def accept_game(r):
    r.motion_gate()
    r.require_confirmation(
        "Confirme C1-C13 verificados, Mode2, seis Assignments, Robotiq cargado, "
        "Tool Z -60 mm, suministro y parada física; cierre otros clientes Modbus"
    )
    full_game = r.confirm("¿Validar una partida completa? YES: partida; no: un turno humano+robot")
    r.current_observed.update(scope="full_game" if full_game else "one_turn",
                              runtime_test_executed=False, completed_robot_turns=0)
    r.require_confirmation("Retire todas las fichas y manos; confirme tablero vacío para iniciar C14")
    session = GameSession(human_first=True)
    client = RecordedClient(r, r.modbus_factory(r.app_config.robot_host, port=r.app_config.robot_port))
    runtime = PhysicalGameRuntime(session, client, manage_connection=True,
                                  timeout=r.timeout, clock=r.clock)
    observer = r.observer_factory(r.vision_config.observer)
    detector = r.detector_factory(r.vision_config.aruco.dictionary, r.app_config.aruco_profile)

    with r.opened_camera() as (camera, settings):
        def flush():
            for _ in range(3):
                r.check_abort()
                with r.stage("camera_read"):
                    camera.read()

        def observe():
            r.check_abort()
            with r.stage("camera_read"):
                frame = camera.read()
            with r.stage("aruco_detection"):
                visible = detector.detect(frame).id_set
            with r.stage("observer"):
                observer.update(visible, timestamp=r.clock())
            return observer.state

        try:
            flush()
            deadline = r.clock() + r.window
            while r.clock() < deadline:
                state = observe()
                r.sleep(0.01)
            if not runtime.start(state):
                raise RuntimeError("C14 requires a stable empty board")
            r.current_observed["runtime_test_executed"] = True
            while session.is_active:
                r.require_confirmation("Autoriza observación de la próxima jugada humana; no coloque más de una ficha")
                flush()
                r.emit("Coloque una ficha humana y retire la mano. Esperando ocupación estable.")
                deadline = r.clock() + max(60.0, r.timeout)
                human_cell = None
                while human_cell is None and r.clock() < deadline:
                    human_cell = runtime.update_board(observe())
                    r.sleep(0.01)
                if human_cell is None:
                    raise TimeoutError("No stable human move observed")
                turn = {"human_cell": human_cell}
                r.current_observed.setdefault("turns", []).append(turn)
                if not session.is_active:
                    break
                r.require_confirmation(
                    "Autoriza UN turno del robot: ficha disponible en PICK, zona sin manos, "
                    "pick/place/HOME; no se reintentará automáticamente"
                )
                flush()
                # Recheck after operator input before allowing a command.
                observer, before = r._sample_open_camera(camera, settings, detector,
                                                         observer=observer)
                expected = frozenset(i for i in range(1, 10) if session.board.cell(i) is not None)
                if not observer.state.ready or observer.state.uncertain_cells or observer.state.occupied_cells != expected:
                    raise RuntimeError("Board changed before robot authorization")
                turn["before_robot"] = before
                while runtime.state not in (RuntimeState.WAITING_HUMAN, RuntimeState.GAME_OVER, RuntimeState.ERROR):
                    state = observe()
                    if runtime.state == RuntimeState.VERIFYING_ROBOT:
                        turn["verified_occupied"] = sorted(state.occupied_cells)
                        runtime.update_board(state)
                    else:
                        runtime.poll_robot()
                    if session.pending_robot_move is not None:
                        if "robot_cell" not in turn:
                            r.emit(f"Robot: CELL{session.pending_robot_move}; esperando BUSY, DONE y verificación visual.")
                        turn["robot_cell"] = session.pending_robot_move
                    r.sleep(0.02)
                if runtime.state == RuntimeState.ERROR:
                    r.current_observed["runtime_error"] = runtime.last_error
                    raise runtime.error_cause or RuntimeError("C14 runtime failed")
                # READY has been read and socket closed before this question.
                if not r.confirm("¿La ficha quedó en la celda indicada y el robot retornó físicamente a HOME?"):
                    raise RuntimeError("Operator rejected robot result")
                turn["home_confirmed"] = True
                r.current_observed["completed_robot_turns"] += 1
                if not full_game:
                    if not r.confirm("Turno verificado. ¿Continuar esta misma partida completa con autorización por movimiento?"):
                        break
                    full_game = True
                    r.current_observed["scope"] = "full_game"
            r.current_observed.update(final_runtime_state=runtime.state.value,
                                      game_result=session.result, board=list(session.board.cells))
        finally:
            if runtime.state not in (RuntimeState.WAITING_HUMAN, RuntimeState.GAME_OVER):
                runtime.stop("C14_STOPPED", runtime.error_cause)
