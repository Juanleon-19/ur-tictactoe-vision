"""Operator-requested COMMAND0 acknowledgement; never a motion or stop command."""

from dataclasses import dataclass
from time import monotonic, sleep
import math

from ur_tictactoe.communication.protocol import STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_ERROR


BUSY_WARNING = "Robot en movimiento. COMMAND0 no es parada. Espere o use la parada física."


@dataclass(frozen=True)
class RecoveryResult:
    ready: bool
    status: int
    message: str


def reset_to_ready(client, *, timeout=3.0, poll_interval=0.05,
                   clock=monotonic, wait=sleep) -> RecoveryResult:
    """Read first, clear exactly once unless BUSY, then poll READY briefly.

    The caller owns connection creation/closure and exclusion with game updates.
    Transport failures propagate: a lost write reply is never retried.
    """
    if not math.isfinite(timeout) or timeout <= 0 or not 0 < poll_interval <= timeout:
        raise ValueError("Invalid recovery timeout or polling interval")
    status = client.read_status()
    if status == STATUS_BUSY:
        return RecoveryResult(False, status, BUSY_WARNING)
    if status not in (STATUS_READY, STATUS_DONE, STATUS_ERROR):
        return RecoveryResult(False, status, f"STATUS129 desconocido: {status}. No se escribió COMMAND0.")
    client.clear_command()  # The only write in this recovery path, never repeated.
    deadline = clock() + timeout
    while clock() < deadline:
        status = client.read_status()
        if clock() >= deadline:
            break
        if status == STATUS_READY:
            return RecoveryResult(True, status, "ROBOT RECUPERADO · READY")
        if status == STATUS_BUSY:
            return RecoveryResult(False, status, BUSY_WARNING)
        if status not in (STATUS_DONE, STATUS_ERROR):
            return RecoveryResult(False, status, f"STATUS129 desconocido tras COMMAND0: {status}.")
        wait(min(poll_interval, max(0, deadline - clock())))
    return RecoveryResult(False, status, f"No se recibió READY en {timeout:g} s. COMMAND0 no se reenvió.")
