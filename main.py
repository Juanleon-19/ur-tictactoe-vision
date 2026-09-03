from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ur_tictactoe.config import load_vision_config
from ur_tictactoe.desktop.tk_app import run_desktop_app
from ur_tictactoe.communication import (
    COMMAND_REGISTER,
    STATUS_BUSY,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_READY,
    ModbusClient,
)
from ur_tictactoe.game import HARD, INTERMEDIATE, Board, O, X, choose_move
from ur_tictactoe.vision.app import run_board_observer, run_move_detection, run_vision
from ur_tictactoe.vision.aruco import ARUCO_PROFILES
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
    vision_parser.add_argument(
        "--aruco-profile",
        choices=ARUCO_PROFILES,
        default="default",
        help="ArUco detector profile (default: default)",
    )
    move_detect_parser = subparsers.add_parser(
        "move-detect", help="Validate human move detection with the camera"
    )
    move_detect_parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "vision.local.yaml",
        help="Path to the local vision YAML configuration",
    )
    board_observe_parser = subparsers.add_parser(
        "board-observe", help="Continuously observe stable physical board occupancy"
    )
    board_observe_parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "vision.local.yaml",
        help="Path to the local vision YAML configuration",
    )
    board_observe_parser.add_argument(
        "--aruco-profile",
        choices=ARUCO_PROFILES,
        default="default",
        help="ArUco detector profile (default: default)",
    )
    move_detect_parser.add_argument(
        "--stable-frames",
        type=int,
        default=5,
        help="Consecutive frames required to confirm a move (default: 5)",
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
    modbus_parser = subparsers.add_parser(
        "modbus-check", help="Read one Modbus STATUS value (read-only by default)"
    )
    modbus_parser.add_argument("--host", required=True, help="Robot or URSim host")
    modbus_parser.add_argument("--port", type=int, default=502)
    modbus_parser.add_argument("--command", type=int, choices=range(1, 10))
    modbus_parser.add_argument(
        "--handshake",
        type=int,
        choices=range(1, 10),
        help="Verify READY/BUSY/DONE/reset without integrating gameplay",
    )
    modbus_parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Explicitly allow writing COMMAND_REGISTER",
    )
    app_parser = subparsers.add_parser("app", help="Open the Windows desktop application")
    app_parser.add_argument(
        "--simulate", action="store_true", help="Run without camera, robot, or sockets"
    )
    return parser


STATUS_NAMES = {
    STATUS_READY: "READY",
    STATUS_BUSY: "BUSY",
    STATUS_DONE: "DONE",
    STATUS_ERROR: "ERROR",
}


def run_modbus_check(args: argparse.Namespace, client_factory=ModbusClient) -> int:
    if args.command is not None and args.handshake is not None:
        print("ERROR: --command and --handshake are mutually exclusive.", file=sys.stderr)
        return 2
    if args.command is not None and not args.allow_write:
        print("ERROR: --command requires --allow-write.", file=sys.stderr)
        return 2

    client = client_factory(args.host, port=args.port)
    try:
        client.connect()
        print("CONNECTION OK")
        status = client.read_status()
        print(f"STATUS = {STATUS_NAMES[status]}")
        if args.handshake is not None:
            if status != STATUS_READY:
                print("ERROR: handshake must start in READY.", file=sys.stderr)
                return 1
            command = args.handshake
            print(f"WRITING COMMAND_REGISTER={COMMAND_REGISTER}: {command}")
            client.write_command(command)
            try:
                if not _wait_for_status(client, STATUS_BUSY):
                    return 1
                if not _wait_for_status(client, STATUS_DONE):
                    return 1
                time.sleep(0.1)
                held = client.read_status()
                print(f"STATUS HELD = {STATUS_NAMES[held]}")
                if held != STATUS_DONE:
                    return 1
            finally:
                print(f"CLEARING COMMAND_REGISTER={COMMAND_REGISTER}: 0")
                client.clear_command()
            return 0 if _wait_for_status(client, STATUS_READY) else 1
        if args.command is not None:
            print(f"WRITING COMMAND_REGISTER={COMMAND_REGISTER}: {args.command}")
            client.write_command(args.command)
        return 0
    finally:
        client.close()


def _wait_for_status(client: ModbusClient, expected: int) -> bool:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        status = client.read_status()
        print(f"STATUS = {STATUS_NAMES[status]}")
        if status == expected:
            return True
        if status == STATUS_ERROR:
            return False
        time.sleep(0.02)
    print(f"ERROR: timeout waiting for {STATUS_NAMES[expected]}.", file=sys.stderr)
    return False


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

    if args.command in ("vision", "move-detect", "board-observe"):
        config_path = args.config
        if not config_path.exists():
            fallback = ROOT / "config" / "vision.example.yaml"
            print(
                f"[INFO] Configuration {config_path} was not found; "
                f"using {fallback}."
            )
            config_path = fallback

        config = load_vision_config(config_path)
        if args.command == "move-detect":
            return run_move_detection(config, args.stable_frames)
        if args.command == "board-observe":
            return run_board_observer(config, args.aruco_profile)
        return run_vision(config, args.aruco_profile)

    if args.command == "cameras":
        return run_camera_discovery()

    if args.command == "game":
        return run_game(args.human_first, args.seed, args.difficulty)

    if args.command == "modbus-check":
        return run_modbus_check(args)

    if args.command == "app":
        return run_desktop_app(args.simulate)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
