"""Public communication interface for the V1 Modbus contract."""

from ur_tictactoe.communication.modbus_client import (
    ModbusClient,
    ModbusConnectionError,
    ModbusResponseError,
)
from ur_tictactoe.communication.protocol import (
    COMMAND_IDLE,
    COMMAND_REGISTER,
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    STATUS_REGISTER,
)

__all__ = [
    "COMMAND_IDLE",
    "COMMAND_REGISTER",
    "ModbusClient",
    "ModbusConnectionError",
    "ModbusResponseError",
    "STATUS_BUSY",
    "STATUS_DONE",
    "STATUS_ERROR",
    "STATUS_READY",
    "STATUS_REGISTER",
]
