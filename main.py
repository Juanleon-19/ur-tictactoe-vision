from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ur_tictactoe.config import load_vision_config
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
    return parser


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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
