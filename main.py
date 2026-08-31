from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ur_tictactoe.config import load_vision_config
from ur_tictactoe.game import (
    EXPERTO,
    HARD,
    INTERMEDIO,
    INTERMEDIATE,
    PICARO,
    PICARO_ACTION,
    Board,
    O,
    X,
    choose_robot_decision,
)
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
        "game", help="Jugar Triqui contra el motor local"
    )
    game_parser.add_argument(
        "--human-first", action="store_true", help="Permitir que el humano empiece como X"
    )
    game_parser.add_argument(
        "--seed", type=int, default=None, help="Semilla para la apertura aleatoria"
    )
    game_parser.add_argument(
        "--difficulty",
        choices=(EXPERTO, INTERMEDIO, PICARO, HARD, INTERMEDIATE),
        default=EXPERTO,
        help="Modo del robot: experto, intermedio o picaro (predeterminado: experto)",
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
        raw_value = input("Tu jugada: ").strip()
        try:
            move = int(raw_value)
            if move not in board.available_moves():
                if not 1 <= move <= 9:
                    print("Elige una celda del 1 al 9.")
                else:
                    print("Esa celda ya está ocupada.")
                continue
            return move
        except ValueError:
            print("Ingresa un número del 1 al 9.")


def run_game(
    human_first: bool = False,
    seed: int | None = None,
    difficulty: str = EXPERTO,
) -> int:
    human, robot = (X, O) if human_first else (O, X)
    turn = X
    board = Board()

    print("TRIQUI — Humano contra Robot")
    print(f"\nRobot: {robot}\nHumano: {human}\n")
    _print_board(board)

    while not board.is_game_over():
        print()
        if turn == human:
            move = _ask_human_move(board)
            board.make_move(move, human)
        else:
            decision = choose_robot_decision(board, robot, human, difficulty, seed)
            if decision is None:
                break
            if decision.action == PICARO_ACTION:
                cells = list(board.cells)
                cells[decision.cell - 1] = robot
                board = Board(cells)
                print(
                    "Robot usa modo PÍCARO: reemplaza la ficha humana "
                    f"de la celda {decision.cell}."
                )
            else:
                board.make_move(decision.cell, robot)
                print(f"Robot juega en la celda {decision.cell}.")
        print()
        _print_board(board)
        turn = O if turn == X else X

    winner = board.winner()
    if winner == robot:
        print("\nGANA EL ROBOT")
    elif winner == human:
        print("\nGANA EL HUMANO")
    else:
        print("\nEMPATE")
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
