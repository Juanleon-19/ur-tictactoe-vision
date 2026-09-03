"""Small orchestration layer for one human-versus-robot game."""

from __future__ import annotations

from ur_tictactoe.game.engine import Board, O, X
from ur_tictactoe.game.minimax import (
    HARD,
    INTERMEDIATE,
    NORMAL_ACTION,
    PICARO,
    PICARO_ACTION,
    RobotDecision,
    choose_robot_decision,
)

HUMAN = "human"
ROBOT = "robot"

ACTIVE = "active"
HUMAN_WINS = "human_wins"
ROBOT_WINS = "robot_wins"
DRAW = "draw"


class GameSession:
    """Coordinate turns while keeping robot decision and execution separate."""

    def __init__(
        self,
        difficulty: str = HARD,
        human_first: bool = False,
        seed: int | None = None,
    ) -> None:
        if difficulty not in (HARD, INTERMEDIATE, PICARO):
            raise ValueError(f"Unknown difficulty: {difficulty}")

        self.board = Board()
        self.difficulty = difficulty
        self.seed = seed
        self.human = X if human_first else O
        self.robot = O if human_first else X
        self.turn: str | None = HUMAN if human_first else ROBOT
        self.pending_robot_move: int | None = None
        self.pending_robot_decision: RobotDecision | None = None
        self.robot_picaro_available = difficulty == PICARO
        self.human_picaro_available = difficulty == PICARO

    @property
    def result(self) -> str:
        winner = self.board.winner()
        if winner == self.human:
            return HUMAN_WINS
        if winner == self.robot:
            return ROBOT_WINS
        if self.board.is_draw():
            return DRAW
        return ACTIVE

    @property
    def is_active(self) -> bool:
        return self.result == ACTIVE

    def play_human_move(self, cell: int) -> None:
        self._require_active()
        if self.turn != HUMAN:
            raise ValueError("It is not the human's turn")

        self.board.make_move(cell, self.human)
        self.turn = None if self.board.is_game_over() else ROBOT

    def play_human_picaro(self, cell: int) -> None:
        """Replace one robot piece during the human turn, consuming the resource."""
        self._require_active()
        if self.turn != HUMAN:
            raise ValueError("It is not the human's turn")
        if self.difficulty != PICARO:
            raise ValueError("Pícaro is not enabled for this game")
        if not self.human_picaro_available:
            raise ValueError("The human Pícaro action has already been used")
        if self.board.cell(cell) != self.robot:
            raise ValueError("The Pícaro target must be a robot cell")

        cells = list(self.board.cells)
        cells[cell - 1] = self.human
        self.board = Board(cells)
        self.human_picaro_available = False
        self.turn = None if self.board.is_game_over() else ROBOT

    def request_robot_move(self) -> int:
        self._require_active()
        if self.turn != ROBOT:
            raise ValueError("It is not the robot's turn")
        if self.pending_robot_decision is not None:
            raise ValueError("A robot move is already pending")

        decision = choose_robot_decision(
            self.board,
            self.robot,
            self.human,
            self.difficulty,
            self.seed,
            self.robot_picaro_available,
        )
        if decision is None:
            raise ValueError("No legal robot move is available")
        self.pending_robot_decision = decision
        self.pending_robot_move = decision.cell
        return decision.cell

    def confirm_robot_move(self) -> None:
        self._require_active()
        if self.pending_robot_decision is None:
            raise ValueError("There is no pending robot move to confirm")

        decision = self.pending_robot_decision
        if decision.action == NORMAL_ACTION:
            self.board.make_move(decision.cell, self.robot)
        elif decision.action == PICARO_ACTION:
            if not self.robot_picaro_available:
                raise ValueError("The robot Pícaro action has already been used")
            if self.board.cell(decision.cell) != self.human:
                raise ValueError("The Pícaro target is no longer a human cell")
            cells = list(self.board.cells)
            cells[decision.cell - 1] = self.robot
            self.board = Board(cells)
            self.robot_picaro_available = False
        self.pending_robot_move = None
        self.pending_robot_decision = None
        self.turn = None if self.board.is_game_over() else HUMAN

    def cancel_robot_move(self) -> None:
        if self.pending_robot_decision is None:
            raise ValueError("There is no pending robot move to cancel")
        self.pending_robot_move = None
        self.pending_robot_decision = None

    def _require_active(self) -> None:
        if not self.is_active:
            raise ValueError("The game is already over")
