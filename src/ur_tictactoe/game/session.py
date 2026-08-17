"""Small orchestration layer for one human-versus-robot game."""

from __future__ import annotations

from ur_tictactoe.game.engine import Board, O, X
from ur_tictactoe.game.minimax import HARD, INTERMEDIATE, choose_move

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
        if difficulty not in (HARD, INTERMEDIATE):
            raise ValueError(f"Unknown difficulty: {difficulty}")

        self.board = Board()
        self.difficulty = difficulty
        self.seed = seed
        self.human = X if human_first else O
        self.robot = O if human_first else X
        self.turn: str | None = HUMAN if human_first else ROBOT
        self.pending_robot_move: int | None = None

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

    def request_robot_move(self) -> int:
        self._require_active()
        if self.turn != ROBOT:
            raise ValueError("It is not the robot's turn")
        if self.pending_robot_move is not None:
            raise ValueError("A robot move is already pending")

        move = choose_move(
            self.board,
            self.robot,
            self.human,
            self.difficulty,
            self.seed,
        )
        if move is None:
            raise ValueError("No legal robot move is available")
        self.pending_robot_move = move
        return move

    def confirm_robot_move(self) -> None:
        self._require_active()
        if self.pending_robot_move is None:
            raise ValueError("There is no pending robot move to confirm")

        self.board.make_move(self.pending_robot_move, self.robot)
        self.pending_robot_move = None
        self.turn = None if self.board.is_game_over() else HUMAN

    def cancel_robot_move(self) -> None:
        if self.pending_robot_move is None:
            raise ValueError("There is no pending robot move to cancel")
        self.pending_robot_move = None

    def _require_active(self) -> None:
        if not self.is_active:
            raise ValueError("The game is already over")
