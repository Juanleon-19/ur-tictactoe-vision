"""Optional CB3 Dashboard diagnostics. No remote actions or Modbus coupling."""

from dataclasses import dataclass
import socket
from time import monotonic
from threading import RLock


@dataclass(frozen=True)
class DashboardSnapshot:
    availability: str = "NO DISPONIBLE"
    program_state: str = "DESCONOCIDO"
    robot_mode: str = "DESCONOCIDO"
    detail: str = "Diagnóstico opcional desactivado."


class DashboardClient:
    """One bounded, fresh TCP 29999 session, with only two fixed queries.

    CB-Series reference: Dashboard_Server_CB-Series.pdf, programState (v1.8)
    and robotmode (v1.6). Both predate CB3 / PolyScope 3.x.
    """

    def __init__(self, host: str, timeout: float = 2.0):
        self.host = host
        self.timeout = timeout
        self._lock = RLock()
        self._connection = None

    @staticmethod
    def _line(connection, deadline):
        data = bytearray()
        while len(data) < 4096:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("Dashboard: tiempo de consulta agotado")
            connection.settimeout(remaining)
            chunk = connection.recv(1)
            if not chunk:
                raise ConnectionError("Dashboard: conexión cerrada sin respuesta completa")
            if chunk == b"\n":
                return data.decode("ascii").strip()
            data.extend(chunk)
        raise ValueError("Dashboard: respuesta demasiado larga")

    def snapshot(self) -> DashboardSnapshot:
        with self._lock:
            try:
                return self._snapshot()
            finally:
                self.close()

    def close(self) -> None:
        """Release a local socket only; never send a Dashboard command."""
        with self._lock:
            connection, self._connection = self._connection, None
            if connection is not None:
                connection.close()

    def _snapshot(self) -> DashboardSnapshot:
        try:
            deadline = monotonic() + self.timeout
            with socket.create_connection((self.host, 29999), timeout=self.timeout) as connection:
                self._connection = connection
                greeting = self._line(connection, deadline)
                if not greeting.startswith("Connected: Universal Robots Dashboard Server"):
                    raise ValueError("Dashboard: saludo no reconocido")
                # No general command API: the bytes sent are fixed, read-only queries.
                connection.sendall(b"programState\n")
                program = self._line(connection, deadline)
                connection.sendall(b"robotmode\n")
                mode = self._line(connection, deadline)
            state = {"PLAYING": "EJECUTANDO", "STOPPED": "DETENIDO", "PAUSED": "PAUSADO"}.get(
                program.split(maxsplit=1)[0] if program else "", "DESCONOCIDO"
            )
            robot_mode = mode.removeprefix("Robotmode: ")
            if robot_mode not in {
                "NO_CONTROLLER", "DISCONNECTED", "CONFIRM_SAFETY", "BOOTING",
                "POWER_OFF", "POWER_ON", "IDLE", "BACKDRIVE", "RUNNING",
            }:
                robot_mode = "DESCONOCIDO"
            return DashboardSnapshot("DISPONIBLE", state, robot_mode,
                                     f"programState: {program}\nrobotmode: {mode}")
        except (OSError, ValueError) as exc:
            return DashboardSnapshot(detail=f"Dashboard 29999: {exc}")
