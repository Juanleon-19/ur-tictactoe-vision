"""Small synchronous Modbus TCP client for the V1 register contract."""

from __future__ import annotations

from typing import Any

from pymodbus.client import ModbusTcpClient

from ur_tictactoe.communication.protocol import (
    COMMAND_IDLE,
    COMMAND_REGISTER,
    STATUS_REGISTER,
    validate_command,
    validate_status,
)


class ModbusConnectionError(RuntimeError):
    """Raised when the Modbus TCP connection cannot be established."""


class ModbusResponseError(RuntimeError):
    """Raised when a Modbus operation returns an invalid or error response."""


class ModbusClient:
    """Access only the command and status registers required by V1."""

    def __init__(
        self,
        host: str,
        port: int = 502,
        timeout: float = 3.0,
        transport: Any | None = None,
    ) -> None:
        if not host:
            raise ValueError("Modbus host must not be empty")
        self._transport = transport or ModbusTcpClient(
            host,
            port=port,
            timeout=timeout,
        )

    def connect(self) -> None:
        try:
            connected = self._transport.connect()
        except Exception as exc:
            raise ModbusConnectionError("Could not connect to Modbus TCP server") from exc
        if not connected:
            raise ModbusConnectionError("Could not connect to Modbus TCP server")

    def close(self) -> None:
        self._transport.close()

    def read_status(self) -> int:
        response = self._transport.read_holding_registers(STATUS_REGISTER, count=1)
        self._require_valid_response(response, "read STATUS")
        registers = getattr(response, "registers", None)
        if not registers or len(registers) != 1:
            raise ModbusResponseError("Modbus response did not contain one STATUS register")
        return validate_status(registers[0])

    def write_command(self, cell: int) -> None:
        command = validate_command(cell)
        response = self._transport.write_register(COMMAND_REGISTER, command)
        self._require_valid_response(response, "write COMMAND")

    def clear_command(self) -> None:
        self.write_command(COMMAND_IDLE)

    @staticmethod
    def _require_valid_response(response: Any, operation: str) -> None:
        if response is None or response.isError():
            raise ModbusResponseError(f"Modbus operation failed: {operation}")
