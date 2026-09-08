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
    _, values = r.sample()
    r.current_observed.update(values)
    if any(percent == 0 for percent in r.current_observed["visibility_percent"].values()):
        raise RuntimeError("Missing operational markers")
    r.current_comments.append("PASS indica cada ID visto al menos una vez; revisar porcentajes, especialmente ID18.")


class _ReadOnlyBoundary:
    def __getattr__(self, name):
        raise RuntimeError("C3 must not perform robot I/O")


def exact_board(r, expected, observer=None):
    observer, values = r.sample(observer=observer)
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
    observer = exact_board(r, set())
    r.require_confirmation("Ponga una ficha en CELL5 y retire la mano")
    observer = exact_board(r, {5}, observer)
    r.require_confirmation("Deje exactamente fichas en CELL1, CELL5 y CELL9; retire la mano")
    exact_board(r, {1, 5, 9}, observer)


def occlusion(r):
    r.require_confirmation("Retire todas las fichas y manos; establecer tablero vacío")
    observer = exact_board(r, set())
    r.require_confirmation("Tras responder YES, pase la mano brevemente durante la captura y retírela")
    observer, values = r.sample(observer=observer)
    r.current_observed.setdefault("observations", []).append(values)
    if all(percent == 100 for percent in values["visibility_percent"].values()):
        raise Blocked("No se observó pérdida de marcadores durante el gesto; repetir C5")
    # Capture a separate recovery window; do not reset temporal history.
    r.emit("Recuperación: mantenga el tablero vacío y sin manos.")
    exact_board(r, set(), observer)
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
        "GEOMETRY_CONFIGURED, ORIENTATION_CONFIGURED y Z_SAFE verificados físicamente; "
        "parada física disponible. El PC no cambia estos parámetros"
    )
    client = r.connect()
    try:
        for cell in cells:
            r.require_confirmation(f"Autoriza movimiento a CELL{cell} a altura segura y acuse COMMAND0")
            handshake(r, client, cell)
            if not r.confirm(f"¿Robot terminó sobre CELL{cell} a altura segura?"):
                raise RuntimeError("Operator rejected physical position")
    finally:
        client.close()


def robotiq(r):
    r.current_observed.update(robotiq_configured=False, model="unknown", urcap_version="unknown")
    raise Blocked("Integración Robotiq pendiente: modelo/URCap e initialize/open/close sin implementar")


def pick_place(r):
    r.current_observed.update(robotiq_configured=False, physical_poses_verified=False)
    raise Blocked("Sin integración Robotiq real ni poses físicas verificadas; no se ejecuta pick/place/end-to-end")


STEPS = {
    "C0": ("SOFTWARE", software), "C1": ("CAMERA", camera),
    "C2": ("ARUCO 10..18", aruco), "C3": ("BOARD EMPTY", empty_board),
    "C4": ("OCCUPANCY", occupancy), "C5": ("OCCLUSION", occlusion),
    "C6": ("MODBUS CONNECTIVITY — READ ONLY", connectivity),
    "C7": ("MODE0 HANDSHAKE", mode0),
    "C8": ("CELL5 SAFE", lambda r: safe_grid(r, [5])),
    "C9": ("GRID SAFE", lambda r: safe_grid(r, range(1, 10))),
    "C10": ("ROBOTIQ", robotiq), "C11": ("PICK", pick_place),
    "C12": ("PLACE CELL5", pick_place), "C13": ("PLACE OTHER CELLS", pick_place),
    "C14": ("END-TO-END", pick_place),
}
