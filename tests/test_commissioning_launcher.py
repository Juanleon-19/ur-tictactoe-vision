"""Exercise PowerShell argument routing without starting Python or hardware."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


def launch_preview(*args):
    powershell = shutil.which("powershell")
    assert powershell, "Windows PowerShell is required for launcher acceptance"
    script = Path(__file__).resolve().parents[1] / "scripts/run_commissioning.ps1"
    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(script), *args, "-DryRun"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["arguments"]


@pytest.mark.parametrize("group, steps", [
    (1, ["C0"]), (2, ["C1", "C2", "C3", "C4", "C5"]), (3, ["C6"]),
    (4, ["C7"]), (5, ["C8"]), (6, ["C9"]), (7, [f"C{i}" for i in range(10)]),
])
def test_launcher_routes_groups_without_motion_authorization(group, steps):
    args = launch_preview("-Group", str(group))
    assert args[:3] == ["-m", "ur_tictactoe.commissioning", "--steps"]
    assert args[3:args.index("--text-report")] == steps
    assert "--allow-motion" not in args
    assert "YES" not in args


def test_launcher_forwards_only_explicit_motion_and_preserves_paths():
    args = launch_preview("-Group", "7", "-AllowMotion", "-Config", "config with spaces.yaml")
    assert args.count("--allow-motion") == 1
    assert args[args.index("--config") + 1] == "config with spaces.yaml"
    assert "YES" not in args
