from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ur_tictactoe.config import load_vision_config
from ur_tictactoe.game import HARD, INTERMEDIATE, Board, O, X, choose_move
from ur_tictactoe.vision.app import run_vision
from ur_tictactoe.vision.camera_discovery import run_camera_discovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UR Tic-Tac-Toe Vision development tools"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    vision_parser = subparsers.add_parser(
        "vision", help="Open the camera and detect ArUco markers"
    )
    vision_parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "vision.local.yaml",
        help="Path to the local vision YAML configuration",
    )
    subparsers.add_parser(
        "cameras", help="List Windows camera devices and probe OpenCV backends"
    )
    game_parser = subparsers.add_parser(
        "game", help="Play Tic-Tac-Toe against the standalone game engine"
    )
    game_parser.add_argument(
        "--human-first", action="store_true", help="Let the human play first as X"
    )
    game_parser.add_argument(
        "--seed", type=int, default=None, help="Seed for the robot's random opening"
    )
    game_parser.add_argument(
        "--difficulty",
        choices=(HARD, INTERMEDIATE),
        default=HARD,
        help="Robot difficulty (default: hard)",
    )
    return parser


def _print_board(board: Board) -> None:
    values = [board.cell(cell) or str(cell) for cell in range(1, 10)]
    for row in range(3):
        start = row * 3
        print(f" {values[start]} | {values[start + 1]} | {values[start + 2]}")
        if row < 2:
            print("---+---+---")


def _ask_human_move(board: Board) -> int:
    while True:
        raw_value = input("Your move: ").strip()
        try:
            move = int(raw_value)
            if move not in board.available_moves():
                if not 1 <= move <= 9:
                    print("Choose a cell from 1 to 9.")
                else:
                    print("That cell is already occupied.")
                continue
            return move
        except ValueError:
            print("Enter a number from 1 to 9.")


def run_game(
    human_first: bool = False,
    seed: int | None = None,
    difficulty: str = HARD,
) -> int:
    human, robot = (X, O) if human_first else (O, X)
    turn = X
    board = Board()

    print("TRIQUI — Human vs Robot")
    print(f"\nRobot: {robot}\nHuman: {human}\n")
    _print_board(board)

    while not board.is_game_over():
        print()
        if turn == human:
            move = _ask_human_move(board)
            board.make_move(move, human)
        else:
            move = choose_move(board, robot, human, difficulty, seed)
            if move is None:
                break
            board.make_move(move, robot)
            print(f"Robot plays: {move}")
        print()
        _print_board(board)
        turn = O if turn == X else X

    winner = board.winner()
    if winner == robot:
        print("\nROBOT WINS")
    elif winner == human:
        print("\nHUMAN WINS")
    else:
        print("\nDRAW")
    return 0


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "vision":
        config_path = args.config
        if not config_path.exists():
            fallback = ROOT / "config" / "vision.example.yaml"
            print(
                f"[INFO] Configuration {config_path} was not found; "
                f"using {fallback}."
            )
            config_path = fallback

        config = load_vision_config(config_path)
        return run_vision(config)

    if args.command == "cameras":
        return run_camera_discovery()

    if args.command == "game":
        return run_game(args.human_first, args.seed, args.difficulty)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
