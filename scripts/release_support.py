"""Local packaging helpers. No camera, robot or GUI is instantiated here."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageOps
import yaml

ROOT = Path(__file__).resolve().parents[1]


def build_icon(root: Path = ROOT) -> Path:
    """Keep the entire approved logo and its aspect ratio on a square canvas."""
    target = root / "build/assets/RobotTriqui.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(root / "assets/javeriana_logo.png") as source:
        logo = ImageOps.contain(source.convert("RGBA"), (256, 256), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    canvas.alpha_composite(logo, ((256 - logo.width) // 2, (256 - logo.height) // 2))
    canvas.save(target, format="ICO", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    return target


def stage_config(root: Path, bundle: Path) -> dict:
    """Copy only the two selected YAML files; rewrite a path in the COPY only."""
    config_dir = bundle / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    selected = {}
    for name in ("app", "vision"):
        source = root / f"config/{name}.local.yaml"
        local = source.is_file()
        if not local:
            source = root / f"config/{name}.example.yaml"
        if not source.is_file():
            raise FileNotFoundError(f"Missing local and example {name} configuration")
        selected[name] = "local" if local else "example"
        shutil.copyfile(source, config_dir / f"{name}.yaml")
    app_path = config_dir / "app.yaml"
    raw = yaml.safe_load(app_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("App configuration must be a mapping")
    # Frozen settings resolve relative to app.yaml, not to the current directory.
    # Absolute developer paths and *.local.yaml must not escape the distribution.
    raw["vision_config"] = "vision.yaml"
    app_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    sys.path.insert(0, str(root / "src"))
    from ur_tictactoe.desktop.settings import load_app_config
    from ur_tictactoe.config import load_vision_config
    config = load_app_config(app_path)
    assert config.vision_config_path.resolve() == (config_dir / "vision.yaml").resolve()
    load_vision_config(config.vision_config_path)  # Parsing only, never opens hardware.
    return {"configuration": selected, "generic": "example" in selected.values()}


def audit_bundle(bundle: Path) -> dict:
    import pefile
    forbidden = {"reports", ".git", "tests", "__pycache__", ".pytest_cache", ".gui-test-cache"}
    files = [p for p in bundle.rglob("*") if p.is_file()]
    for path in files:
        relative = path.relative_to(bundle)
        if forbidden.intersection(relative.parts) or ".local." in path.name or path.suffix == ".log":
            raise ValueError(f"Forbidden distribution content: {relative}")
    for relative in ("RobotTriqui.exe", "_internal/python312.dll", "_internal/assets/javeriana_logo.png",
                     "_internal/assets/RobotTriqui.ico", "config/app.yaml", "config/vision.yaml"):
        if not (bundle / relative).is_file():
            raise FileNotFoundError(f"Required distribution file missing: {relative}")
    with pefile.PE(str(bundle / "RobotTriqui.exe")) as executable:
        if executable.OPTIONAL_HEADER.Subsystem != 2:
            raise ValueError("Executable must use Windows GUI subsystem (no console)")
        if not any(entry.id == 14 for entry in executable.DIRECTORY_ENTRY_RESOURCE.entries):
            raise ValueError("Executable icon resource missing")
    return {"files": len(files), "bytes": sum(p.stat().st_size for p in files), "gui_subsystem": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("stage", "audit"))
    args = parser.parse_args()
    bundle = ROOT / "dist/RobotTriqui"
    result = stage_config(ROOT, bundle) if args.action == "stage" else audit_bundle(bundle)
    # Evidence contains provenance only, never IPs or local YAML contents.
    evidence = ROOT / f"build/{args.action}-result.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
