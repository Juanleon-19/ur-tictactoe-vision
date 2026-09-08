"""GUI-first entrypoint shared by the Windows executable."""

import argparse
from pathlib import Path

from ur_tictactoe.desktop.tk_app import run_desktop_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Robot Triqui desktop")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--config", type=Path, help="External application YAML")
    args = parser.parse_args(argv)
    return run_desktop_app(args.simulate, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
