from __future__ import annotations

import sys
from pathlib import Path

import main as main_module


def test_move_detect_cli_defaults() -> None:
    args = main_module.build_parser().parse_args(["move-detect"])
    assert args.subcommand == "move-detect"
    assert args.stable_frames == 5


def test_move_detect_cli_accepts_configurable_stable_frames() -> None:
    args = main_module.build_parser().parse_args(
        ["move-detect", "--stable-frames", "8"]
    )
    assert args.stable_frames == 8


def test_move_detect_dispatches_config_and_stable_frames(monkeypatch) -> None:
    config_path = Path("config/vision.example.yaml")
    sentinel_config = object()
    received: list[tuple[object, int]] = []

    monkeypatch.setattr(sys, "argv", ["main.py", "move-detect", "--config", str(config_path)])
    monkeypatch.setattr(main_module, "load_vision_config", lambda path: sentinel_config)
    monkeypatch.setattr(
        main_module,
        "run_move_detection",
        lambda config, stable_frames: received.append((config, stable_frames)) or 0,
    )

    assert main_module.main() == 0
    assert received == [(sentinel_config, 5)]


def test_board_observer_defaults_to_robust_and_allows_default(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(main_module, "run_board_observer",
                        lambda config, profile: calls.append(profile) or 0)
    for flags, expected in (([], "robust"), (["--aruco-profile", "default"], "default")):
        monkeypatch.setattr(main_module.sys, "argv", ["main.py", "board-observe", *flags])
        assert main_module.main() == 0
        assert calls[-1] == expected
