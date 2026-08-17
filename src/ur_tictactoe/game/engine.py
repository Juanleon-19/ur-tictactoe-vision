"""Rules and board state for a 3x3 game of Tic-Tac-Toe."""

from __future__ import annotations

from collections.abc import Sequence

X = "X"
O = "O"
EMPTY = None
PLAYERS = (X, O)

WINNING_LINES = (
    (1, 2, 3),
    (4, 5, 6),
    (7, 8, 9),
    (1, 4, 7),
    (2, 5, 8),
    (3, 6, 9),
    (1, 5, 9),
    (3, 5, 7),
)


class Board:
    """Mutable 3x3 board whose public cell numbers are always 1 through 9."""

    def __init__(self, cells: Sequence[str | None] | None = None) -> None:
        values = [EMPTY] * 9 if cells is None else list(cells)
        if len(values) != 9:
            raise ValueError("A board must contain exactly 9 cells")
        if any(value not in (EMPTY, X, O) for value in values):
            raise ValueError("Board cells must be X, O, or empty")
        self._cells = values

    @property
    def cells(self) -> tuple[str | None, ...]:
        return tuple(self._cells)

    def copy(self) -> Board:
        return Board(self._cells)

    def cell(self, number: int) -> str | None:
        self._validate_cell_number(number)
        return self._cells[number - 1]

    def available_moves(self) -> list[int]:
        return [number for number in range(1, 10) if self.cell(number) is EMPTY]

    def make_move(self, number: int, player: str) -> None:
        self._validate_cell_number(number)
        if player not in PLAYERS:
            raise ValueError("Player must be X or O")
        if self.cell(number) is not EMPTY:
            raise ValueError(f"Cell {number} is already occupied")
        if self.is_game_over():
            raise ValueError("The game is already over")
        self._cells[number - 1] = player

    def winner(self) -> str | None:
        for first, second, third in WINNING_LINES:
            player = self.cell(first)
            if player is not EMPTY and player == self.cell(second) == self.cell(third):
                return player
        return None

    def is_draw(self) -> bool:
        return self.winner() is None and not self.available_moves()

    def is_game_over(self) -> bool:
        return self.winner() is not None or self.is_draw()

    @staticmethod
    def _validate_cell_number(number: int) -> None:
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 9:
            raise ValueError("Cell number must be an integer from 1 to 9")
