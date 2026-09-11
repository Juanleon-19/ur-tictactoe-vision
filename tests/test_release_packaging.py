"""Packaging uses fixture configs and image files; never opens physical devices."""
import importlib.util
from pathlib import Path
import subprocess

import pytest
import yaml
from PIL import Image

from ur_tictactoe.desktop import settings

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_support", ROOT / "scripts/release_support.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("local_app,local_vision", [(True, True), (True, False), (False, True), (False, False)])
def test_config_selection_preserves_sources_and_resolves_after_install(tmp_path, monkeypatch, local_app, local_vision):
    source = tmp_path / "source"
    config_dir = source / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "app.example.yaml").write_text("robot: {host: ''}\n", encoding="utf-8")
    (config_dir / "vision.example.yaml").write_text("camera: {index: 0}\n", encoding="utf-8")
    if local_app:
        (config_dir / "app.local.yaml").write_text(
            "robot: {host: robot.example}\nvision_config: C:/not-portable/vision.local.yaml\n",
            encoding="utf-8")
    if local_vision:
        (config_dir / "vision.local.yaml").write_text("camera: {index: 2, backend: MSMF}\n", encoding="utf-8")
    originals = {p: p.read_bytes() for p in config_dir.iterdir()}
    installed = tmp_path / "Programs/Robot Triqui"
    result = release.stage_config(source, installed)
    assert result == {"configuration": {"app": "local" if local_app else "example",
                                        "vision": "local" if local_vision else "example"},
                      "generic": not (local_app and local_vision)}
    assert originals == {p: p.read_bytes() for p in config_dir.iterdir()}
    assert sorted(p.name for p in (installed / "config").iterdir()) == ["app.yaml", "vision.yaml"]
    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings.sys, "executable", str(installed / "RobotTriqui.exe"))
    monkeypatch.chdir(tmp_path)
    app = settings.load_app_config()
    assert app.robot_host == ("robot.example" if local_app else "")
    assert app.vision_config_path == installed / "config/vision.yaml"
    vision = yaml.safe_load(app.vision_config_path.read_text(encoding="utf-8"))
    assert vision["camera"]["index"] == (2 if local_vision else 0)


def test_missing_example_is_not_replaced_with_invented_configuration(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing local and example"):
        release.stage_config(tmp_path, tmp_path / "dist")


def test_icon_preserves_approved_png_and_contains_all_sizes(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    original = (ROOT / "assets/javeriana_logo.png").read_bytes()
    (assets / "javeriana_logo.png").write_bytes(original)
    icon = release.build_icon(tmp_path)
    with Image.open(icon) as image:
        assert image.ico.sizes() == {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)}
        assert image.ico.getimage((256, 256)).getbbox() == (0, 64, 256, 192)
    assert (assets / "javeriana_logo.png").read_bytes() == original


def test_build_refuses_wrong_directory_before_cleaning(tmp_path):
    sentinel = tmp_path / "dist/keep.txt"
    sentinel.parent.mkdir()
    sentinel.write_text("keep")
    result = subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "scripts/build_release.ps1")],
                            cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and "repository root" in result.stderr
    assert sentinel.read_text() == "keep"


def test_installer_never_launches_application_and_is_per_user():
    text = (ROOT / "installer/RobotTriqui.iss").read_text(encoding="utf-8-sig")
    directives = [line.strip() for line in text.splitlines() if not line.lstrip().startswith(";")]
    assert "PrivilegesRequired=lowest" in directives
    assert "DefaultDirName={localappdata}\\Programs\\Robot Triqui" in directives
    assert "[Run]" not in directives and "[UninstallRun]" not in directives
    assert "UninstallDisplayIcon={app}\\RobotTriqui.exe" in directives
