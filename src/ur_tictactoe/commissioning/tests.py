"""Independent operator procedures; no game or trajectory implementation."""

from importlib.metadata import version, PackageNotFoundError
import platform
import xml.etree.ElementTree as ET

from ur_tictactoe.communication import STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_ERROR
from ur_tictactoe.game import GameSession
from ur_tictactoe.runtime import PhysicalGameRuntime
from .runner import Blocked


def software(r):
    dependencies = {}
    for package in ("opencv-contrib-python", "numpy", "PyYAML", "pymodbus", "customtkinter", "Pillow"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "MISSING"
    r.current_observed.update(python=platform.python_version(), dependencies=dependencies,
                              configuration_loaded=True, software_tests="UNKNOWN")
    if "MISSING" in dependencies.values():
        raise RuntimeError("Missing dependencies")
    if r.test_evidence is None:
        raise Blocked("Sin evidencia de pytest; use --pytest-report con el JUnit XML de esta versión")
    root = ET.parse(r.test_evidence).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {key: sum(int(s.get(key, "0")) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    r.current_observed["software_tests"] = totals
    r.current_comments.append("Evidencia externa de pytest suministrada por el operador; verificar SHA/fecha.")
    if not totals["tests"] or totals["failures"] or totals["errors"]:
        raise RuntimeError("Software tests not green")


def camera(r):
    r.sample_camera()


def aruco(r):
    _, values = r.sample(preview=True)
    r.current_observed.update(values)
    if any(percent == 0 for percent in r.current_observed["visibility_percent"].values()):
        raise RuntimeError("Missing operational markers")
    r.current_comments.append("PASS indica cada ID visto al menos una vez; revisar porcentajes, especialmente ID18.")


class _ReadOnlyBoundary:
    def __getattr__(self, name):
        raise RuntimeError("C3 must not perform robot I/O")


def exact_board(r, expected, observer=None, *, sample=None):
    observer, values = (sample or r.sample)(observer=observer)
    r.current_observed.setdefault("observations", []).append(values)
    state = observer.state
    if not state.ready or state.uncertain_cells or state.occupied_cells != frozenset(expected):
        raise RuntimeError("Board did not reach the exact expected stable state")
    return observer


def empty_board(r):
    r.require_confirmation("Retire todas las fichas y manos; tablero vacío 1..9")
    observer = exact_board(r, set())
    # Reuse the production acceptance gate, with a boundary that forbids I/O.
    runtime = PhysicalGameRuntime(GameSession(human_first=True), _ReadOnlyBoundary())
    accepted = runtime.start(observer.state)
    r.current_observed["physical_runtime_start"] = accepted
    if not accepted:
        raise RuntimeError("Runtime rejected empty board")


def occupancy(r):
    r.require_confirmation("Retire todas las fichas y manos para establecer la referencia vacía")
    with r.camera_samples() as sample:
        observer = exact_board(r, set(), sample=sample)
        r.require_confirmation("Ponga una ficha en CELL5 y retire la mano")
        observer = exact_board(r, {5}, observer, sample=sample)
        r.require_confirmation("Deje exactamente fichas en CELL1, CELL5 y CELL9; retire la mano")
        exact_board(r, {1, 5, 9}, observer, sample=sample)


def occlusion(r):
    r.require_confirmation("Retire todas las fichas y manos; establecer tablero vacío")
    with r.camera_samples() as sample:
        observer = exact_board(r, set(), sample=sample)
        r.require_confirmation("Tras responder YES, pase la mano brevemente durante la captura y retírela")
        observer, values = sample(observer=observer)
        r.current_observed.setdefault("observations", []).append(values)
        if all(percent == 100 for percent in values["visibility_percent"].values()):
            raise Blocked("No se observó pérdida de marcadores durante el gesto; repetir C5")
        # Capture a separate recovery window; do not reset temporal history.
        r.emit("Recuperación: mantenga el tablero vacío y sin manos.")
        exact_board(r, set(), observer, sample=sample)
        r.require_confirmation("¿Pasó la mano brevemente durante la ventana de captura?")


def connectivity(r):
    client = r.connect()
    try:
        r.check_abort()
        with r.stage("modbus_read"):
            r.current_observed.update(tcp_connected=True, register=129, status129=client.read_status())
    finally:
        client.close()


def handshake(r, client, cell):
    """Protocol acceptance measures all transitions, including DONE held/reset.

    This tests the controller directly, not a game turn: runtime verification
    requires a placed piece and therefore cannot validate safe-height Mode 0/1.
    """
    trace = {"cell": cell, "transitions": []}
    r.current_observed.setdefault("handshakes", []).append(trace)
    start = r.clock()

    def read():
        r.check_abort()
        status = client.read_status()
        trace["transitions"].append({"status": status, "seconds": r.clock() - start})
        if status == STATUS_ERROR:
            raise RuntimeError("Controller ERROR")
        return status

    def wait(expected, allowed):
        deadline = r.clock() + r.timeout
        while r.clock() < deadline:
            status = read()
            if status == expected:
                return
            if status not in allowed:
                raise RuntimeError("Unexpected status transition")
            r.sleep(0.02)
        raise TimeoutError("Controller transition timeout")

    if read() != STATUS_READY:
        raise RuntimeError("Controller not READY")
    r.motion_gate()
    client.write_command(cell)
    trace["command_sent"] = True
    # On interruption/error never attempt an automatic retry or a new command.
    # COMMAND0 is an acknowledgement, not an emergency stop.
    wait(STATUS_BUSY, {STATUS_READY})
    wait(STATUS_DONE, {STATUS_BUSY})
    deadline = r.clock() + r.hold
    while r.clock() < deadline:
        if read() != STATUS_DONE:
            raise RuntimeError("DONE not held")
        r.sleep(0.02)
    trace["done_held_seconds"] = r.hold
    r.motion_gate()
    client.clear_command()
    trace["command_cleared"] = True
    wait(STATUS_READY, {STATUS_DONE})


def mode0(r):
    r.motion_gate()
    r.require_confirmation("Confirme robot ejecutando triqui_controller.script con MOTION_MODE=0; autoriza COMMAND5 y COMMAND0")
    client = r.connect()
    try:
        handshake(r, client, 5)
    finally:
        client.close()


def safe_grid(r, cells):
    r.motion_gate()
    r.require_confirmation(
        "Confirme MOTION_MODE=1 configurado manualmente en el robot, "
        "Assignments P1/P3/P7/P9 verificados; Pn_UP usa Tool Z -60 mm; "
        "parada física disponible. El PC no cambia estos parámetros"
    )
    for cell in cells:
        r.require_confirmation(f"Autoriza movimiento a CELL{cell} (P{cell}_UP) y acuse COMMAND0")
        client = r.connect()
        try:
            handshake(r, client, cell)
        finally:
            client.close()
        if not r.confirm(f"¿Robot terminó sobre CELL{cell} en P{cell}_UP sin descenso?"):
            raise RuntimeError("Operator rejected physical position")


def robotiq(r):
    r.current_observed.update(robotiq_configured=False, evidence="operator_confirmation")
    r.require_confirmation("Confirme que el programa PolyScope incluye las definiciones rq_* del URCap Robotiq instalado")
    r.require_confirmation("Confirme que activación y open/close Robotiq fueron comprobados físicamente sin error; este paso no mueve el brazo")
    r.current_observed.update(robotiq_configured=True, open_close_verified=True)


def pick(r):
    r.current_observed.update(pick_verified=False, evidence="operator_confirmation")
    r.require_confirmation("Confirme Assignments P_PICK/P_HOME y aproximación Tool Z -60 mm verificados en PolyScope")
    r.require_confirmation("Confirme ensayo manual ya realizado: PICK + close + retract a P_PICK_UP, con ficha agarrada y sin colisión")
    r.current_observed.update(pick_verified=True, close_retract_verified=True)
    r.current_comments.append("Evidencia manual; no se envió COMMAND ni existe un comando PICK separado")


def pick_place(r, cells):
    r.motion_gate()
    r.require_confirmation(
        "Confirme MOTION_MODE=2 en el robot, Assignments P1/P3/P7/P9/P_PICK/P_HOME, "
        "C8-C11 verificados, Robotiq cargado y parada física disponible; el PC no cambia el modo"
    )
    for cell in cells:
        r.require_confirmation(
            f"Confirme CELL{cell} libre, ficha disponible en PICK y zona sin manos; "
            f"autoriza COMMAND{cell}: pick → place CELL{cell} → HOME y acuse COMMAND0"
        )
        client = r.connect()
        try:
            handshake(r, client, cell)
        finally:
            client.close()
        if not r.confirm(f"¿La ficha quedó físicamente en CELL{cell} y el robot retornó a P_HOME?"):
            raise RuntimeError("Operator rejected physical placement")
        r.current_observed.setdefault("placements_verified", []).append(cell)


def end_to_end(r):
    r.current_observed.update(runtime_test_executed=False, prerequisites_verified=False)
    r.require_confirmation("Confirme evidencia vigente C1-C13, tablero vacío y estable, suministro de fichas y parada física disponible")
    r.require_confirmation("Confirme MOTION_MODE=2, seis Assignments vigentes y cliente de commissioning exclusivo; cerrar otros clientes Modbus")
    r.current_observed.update(prerequisites_verified=True,
                              pending="runtime_vision_game_acceptance")
    raise Blocked(
        "C14: precondiciones registradas; pendiente adaptar el procedimiento de partida con "
        "runtime/visión/juego y verificar jugadas humanas, colocaciones y fin de partida. "
        "No se ejecutó una partida ni se enviaron comandos"
    )


STEPS = {
    "C0": ("SOFTWARE", software), "C1": ("CAMERA", camera),
    "C2": ("ARUCO 10..18", aruco), "C3": ("BOARD EMPTY", empty_board),
    "C4": ("OCCUPANCY", occupancy), "C5": ("OCCLUSION", occlusion),
    "C6": ("MODBUS CONNECTIVITY — READ ONLY", connectivity),
    "C7": ("MODE0 HANDSHAKE", mode0),
    "C8": ("CELL5 SAFE", lambda r: safe_grid(r, [5])),
    "C9": ("GRID SAFE", lambda r: safe_grid(r, range(1, 10))),
    "C10": ("ROBOTIQ", robotiq), "C11": ("PICK", pick),
    "C12": ("PLACE CELL5", lambda r: pick_place(r, [5])),
    "C13": ("PLACE OTHER CELLS", lambda r: pick_place(r, [1, 3, 7, 9, 2, 4, 6, 8])),
    "C14": ("END-TO-END", end_to_end),
}
