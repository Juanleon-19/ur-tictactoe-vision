"""Central constants and validation for the project Modbus V1 protocol."""

COMMAND_REGISTER = 128
STATUS_REGISTER = 129

COMMAND_IDLE = 0

STATUS_READY = 0
STATUS_BUSY = 1
STATUS_DONE = 2
STATUS_ERROR = 3

VALID_STATUSES = (STATUS_READY, STATUS_BUSY, STATUS_DONE, STATUS_ERROR)


def validate_command(command: int) -> int:
    if isinstance(command, bool) or not isinstance(command, int) or not 0 <= command <= 9:
        raise ValueError("COMMAND must be an integer from 0 to 9")
    return command


def validate_status(status: int) -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown STATUS value: {status}")
    return status
