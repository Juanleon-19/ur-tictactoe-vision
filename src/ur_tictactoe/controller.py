"""Non-blocking software orchestration for one game cycle."""

from __future__ import annotations

from collections.abc import Iterable

from ur_tictactoe.communication import (
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    ModbusClient,
)
from ur_tictactoe.game import HUMAN, ROBOT, GameSession
from ur_tictactoe.vision.move_detector import HumanMoveDetector


class GameController:
    """Coordinate vision events, game state, and the Modbus handshake."""

    def __init__(
        self,
        move_detector: HumanMoveDetector,
        session: GameSession,
        modbus_client: ModbusClient,
    ) -> None:
        self.move_detector = move_detector
        self.session = session
        self.modbus_client = modbus_client
        self.command_sent = False

    def step(
        self,
        frame_ready: bool,
        visible_cell_ids: Iterable[int],
    ) -> int | None:
        """Process one observation or one Modbus status without blocking."""
        if not self.session.is_active:
            return None

        if self.session.turn == HUMAN:
            human_move = self.move_detector.update(
                visible_cell_ids,
                frame_ready,
                self._occupied_cells(),
            )
            if human_move is not None:
                self.session.play_human_move(human_move)
            return human_move

        if self.session.turn != ROBOT:
            return None

        if self.session.pending_robot_move is None:
            self.session.request_robot_move()

        status = self.modbus_client.read_status()
        if status == STATUS_READY:
            if not self.command_sent:
                self.modbus_client.write_command(self.session.pending_robot_move)
                self.command_sent = True
        elif status == STATUS_BUSY:
            pass
        elif status == STATUS_DONE:
            if self.command_sent:
                self.session.confirm_robot_move()
                self.modbus_client.clear_command()
                self.command_sent = False
        elif status == STATUS_ERROR:
            if self.session.pending_robot_move is not None:
                self.session.cancel_robot_move()
                self.modbus_client.clear_command()
                self.command_sent = False
        return None

    def _occupied_cells(self) -> set[int]:
        return {
            cell
            for cell in range(1, 10)
            if self.session.board.cell(cell) is not None
        }
