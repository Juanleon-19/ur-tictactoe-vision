from pathlib import Path

import pytest

from ur_tictactoe.desktop import settings
from ur_tictactoe import desktop_entry


def test_packaged_defaults_do_not_depend_on_local_config(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "application_directory", lambda: tmp_path)
    config = settings.load_app_config()
    assert config.robot_host == ""
    assert config.robot_port == 502
    assert config.aruco_profile == "robust"
    assert config.vision_config_path.name == "vision.example.yaml"
    assert config.vision_config_path.is_file()


def test_external_config_resolves_relative_to_config_not_cwd(tmp_path):
    path = tmp_path / "app.yaml"
    path.write_text("robot:\n  host: robot.example\n  port: 502\nvision_config: camera.yaml\naruco_profile: default\n")
    config = settings.load_app_config(path)
    assert config.robot_host == "robot.example"
    assert config.vision_config_path == tmp_path / "camera.yaml"
    assert config.aruco_profile == "default"


def test_adjacent_vision_config_takes_precedence(monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    external = tmp_path / "config/vision.yaml"
    external.write_text("camera: {}")
    monkeypatch.setattr(settings, "application_directory", lambda: tmp_path)
    assert settings.load_app_config().vision_config_path == external


@pytest.mark.parametrize("content", ["[]", "false", "0", "''", "robot: []", "aruco_profile: unknown", "robot:\n  port: 0"])
def test_invalid_external_config_is_reported(tmp_path, content):
    path = tmp_path / "app.yaml"
    path.write_text(content)
    with pytest.raises(ValueError):
        settings.load_app_config(path)


@pytest.mark.parametrize("args, simulation", [([], False), (["--simulate"], True)])
def test_executable_entry_dispatches_directly_to_desktop(monkeypatch, args, simulation):
    calls = []
    monkeypatch.setattr(desktop_entry, "run_desktop_app", lambda *values: calls.append(values) or 0)
    assert desktop_entry.main(args) == 0
    assert calls == [(simulation, None)]


def test_executable_accepts_external_config(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop_entry, "run_desktop_app", lambda *values: calls.append(values) or 0)
    assert desktop_entry.main(["--config", "settings.yaml"]) == 0
    assert calls == [(False, Path("settings.yaml"))]
