"""Acceptance of the harness with no sockets, camera or robot."""

import json
from types import SimpleNamespace

import pytest

from ur_tictactoe.commissioning import __main__ as cli
from ur_tictactoe.commissioning.runner import Runner
from ur_tictactoe.config import load_vision_config
from ur_tictactoe.desktop.settings import AppConfig, default_vision_path
from ur_tictactoe.vision.camera import CameraSettings


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Camera:
    def __init__(self, config):
        self.closed = False
        self.effective_settings = CameraSettings(640, 480, 30)

    def open(self):
        pass

    def read(self):
        return object()

    def close(self):
        self.closed = True


class Robot:
    def __init__(self):
        self.writes = []
        self.status = 0
        self.polls = 0
        self.closed = False

    def connect(self):
        pass

    def read_status(self):
        if self.status == 1:
            self.polls += 1
            if self.polls > 1:
                self.status = 2
        return self.status

    def write_command(self, cell):
        self.writes.append(cell)
        self.status = 1 if cell else 0
        self.polls = 0

    def clear_command(self):
        self.write_command(0)

    def close(self):
        self.closed = True


@pytest.fixture
def make_runner(tmp_path):
    def make(answers=None, **options):
        clock, robot, cameras = Clock(), Robot(), []
        visible = set(range(10, 19))
        occlusion_until = [0.0]
        answer_iter = iter(answers) if answers is not None else None

        def ask(message):
            if "Ponga una ficha" in message:
                visible.clear()
                visible.update(set(range(10, 19)) - {14})
            elif "Deje exactamente" in message:
                visible.clear()
                visible.update(set(range(10, 19)) - {10, 14, 18})
            elif "Retire todas" in message:
                visible.update(range(10, 19))
            elif "Tras responder" in message:
                occlusion_until[0] = clock() + 0.15
            return next(answer_iter) if answer_iter else "YES"

        def camera_factory(config):
            camera = Camera(config)
            cameras.append(camera)
            return camera

        evidence = tmp_path / "pytest.xml"
        evidence.write_text('<testsuites><testsuite tests="257" failures="0" errors="0" skipped="0"/></testsuites>')
        kwargs = dict(
            ask=ask, emit=lambda _: None, clock=clock, sleep=clock.sleep,
            camera_factory=camera_factory,
            detector_factory=lambda *args: SimpleNamespace(detect=lambda _: SimpleNamespace(
                id_set=set() if clock() < occlusion_until[0] else visible)),
            modbus_factory=lambda *args, **kwargs: robot,
            test_evidence=evidence, window=3.0, timeout=0.2, hold=0.05,
        )
        kwargs.update(options)
        runner = Runner(AppConfig(robot_host="robot.invalid"), load_vision_config(default_vision_path()), **kwargs)
        runner.fake_robot, runner.fake_cameras, runner.fake_visible = robot, cameras, visible
        return runner
    return make


@pytest.mark.parametrize("step", [f"C{i}" for i in range(7)])
def test_read_only_steps_use_fakes_without_writes(make_runner, step):
    r = make_runner()
    result = r.run([step]).results[0]
    assert result.status == "PASS", result
    assert not r.fake_robot.writes
    assert all(c.closed for c in r.fake_cameras)
    assert r.report.configuration["cell_ids"] == list(range(10, 19))


def test_c1_is_independent_of_detector_and_observer(make_runner):
    def forbidden(*args):
        pytest.fail("C1 must not construct vision processors")
    r = make_runner(detector_factory=forbidden, observer_factory=forbidden)
    result = r.run(["C1"]).results[0]
    assert result.status == "PASS"
    assert result.observed["frames"] > 0
    assert result.observed["elapsed_seconds"] >= r.window
    assert result.observed["camera_index"] == r.vision_config.camera.index
    assert result.observed["backend"] == r.vision_config.camera.backend
    assert result.observed["resolution"] == [640, 480]
    assert result.observed["configured_fps"] == r.vision_config.camera.fps
    assert result.observed["camera_fps"] == 30
    assert result.observed["measured_fps"] == pytest.approx(
        result.observed["frames"] / result.observed["elapsed_seconds"])
    assert not {"board_ready", "visible_ids", "cells", "profile"} & result.observed.keys()
    assert all(c.closed for c in r.fake_cameras)


@pytest.mark.parametrize("stage", ["camera_open", "camera_settings", "camera_read", "camera_close"])
def test_c1_failure_stage_is_safe_and_camera_is_closed(make_runner, stage):
    class BrokenCamera:
        closed = False

        def open(self):
            if stage == "camera_open":
                raise RuntimeError("secret/path/device information")

        @property
        def effective_settings(self):
            if stage == "camera_settings":
                raise RuntimeError("secret/path/device information")
            return CameraSettings(1280, 720, 30)

        def read(self):
            if stage == "camera_read":
                raise RuntimeError("secret/path/device information")
            return object()

        def close(self):
            self.closed = True
            if stage == "camera_close":
                raise RuntimeError("secret/path/device information")

    camera = BrokenCamera()
    r = make_runner(camera_factory=lambda _: camera)
    result = r.run(["C1"]).results[0]
    assert result.status == "FAIL"
    assert result.observed["failure_stage"] == stage
    assert result.observed["error_type"] == "RuntimeError"
    assert camera.closed
    assert "secret" not in str(result)


@pytest.mark.parametrize("frame", [None, SimpleNamespace(size=0)])
def test_c1_rejects_invalid_frames(make_runner, frame):
    camera = Camera(None)
    camera.read = lambda: frame
    r = make_runner(camera_factory=lambda _: camera)
    result = r.run(["C1"]).results[0]
    assert result.status == "FAIL"
    assert result.observed["failure_stage"] == "camera_read"
    assert result.observed["frames"] == 0
    assert camera.closed


def test_c1_acquisition_window_excludes_slow_open_and_has_no_30fps_requirement(make_runner):
    r = make_runner(window=1)
    camera = Camera(None)
    camera.open = lambda: r.sleep(5)

    def read():
        r.sleep(1 / 15)
        return object()

    camera.read = read
    r.camera_factory = lambda _: camera
    result = r.run(["C1"]).results[0]
    assert result.status == "PASS"
    assert 1 <= result.observed["elapsed_seconds"] < 1.1
    assert 14 < result.observed["measured_fps"] < 16
    assert result.duration_seconds >= 6
    assert result.observed["frames"] >= 14
    assert camera.closed


@pytest.mark.parametrize("component, stage", [
    ("detector", "aruco_detection"), ("observer", "observer"),
])
def test_c2_still_runs_vision_and_reports_safe_stages(make_runner, component, stage):
    r = make_runner()
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("secret detector/observer details")

    if component == "detector":
        r.detector_factory = lambda *args: SimpleNamespace(detect=fail)
    else:
        r.observer_factory = lambda *args: SimpleNamespace(update=fail)
    result = r.run(["C2"]).results[0]
    assert calls
    assert result.status == "FAIL"
    assert result.observed["failure_stage"] == stage
    assert "secret" not in str(result)
    assert all(c.closed for c in r.fake_cameras)


@pytest.mark.parametrize("step", ["C7", "C8", "C9"])
def test_motion_requires_flag_before_connect_or_prompt(make_runner, step):
    def forbidden(*args, **kwargs):
        pytest.fail("Permission gate must precede all I/O")
    r = make_runner(ask=forbidden, modbus_factory=forbidden)
    assert r.run([step]).results[0].status == "BLOCKED"
    assert not r.fake_robot.writes


@pytest.mark.parametrize("step", ["C7", "C8", "C9"])
def test_negative_confirmation_prevents_command(make_runner, step):
    r = make_runner(["no"], allow_motion=True)
    assert r.run([step]).results[0].status == "BLOCKED"
    assert not r.fake_robot.writes


def test_mode0_handshake_has_done_hold_and_reset(make_runner):
    r = make_runner(allow_motion=True)
    result = r.run(["C7"]).results[0]
    assert result.status == "PASS"
    assert r.fake_robot.writes == [5, 0]
    trace = result.observed["handshakes"][0]
    statuses = [item["status"] for item in trace["transitions"]]
    assert statuses[:3] == [0, 1, 2]
    assert statuses[-1] == 0
    assert statuses.count(2) >= 2
    assert trace["done_held_seconds"] == 0.05
    assert r.fake_robot.closed


def test_grid_requires_confirmation_for_each_move(make_runner):
    r = make_runner(["YES", "YES", "YES", "no"], allow_motion=True)
    assert r.run(["C9"]).results[0].status == "BLOCKED"
    assert r.fake_robot.writes == [1, 0]


def test_full_grid_has_individual_acceptance(make_runner):
    r = make_runner(allow_motion=True)
    result = r.run(["C9"]).results[0]
    assert result.status == "PASS"
    assert r.fake_robot.writes == [n for cell in range(1, 10) for n in (cell, 0)]
    assert len(result.comments) == 19


def test_abort_prevents_next_move_and_next_step(make_runner):
    r = make_runner(["YES", "YES", "YES", "ABORT"], allow_motion=True)
    assert [x.status for x in r.run(["C9", "C7"]).results] == ["SKIPPED", "SKIPPED"]
    assert r.fake_robot.writes == [1, 0]
    assert r.fake_robot.closed


def test_ctrl_c_during_poll_never_sends_next_action(make_runner):
    r = make_runner(allow_motion=True)
    original = r.fake_robot.read_status
    def read():
        if r.fake_robot.writes:
            raise KeyboardInterrupt()
        return original()
    r.fake_robot.read_status = read
    assert [x.status for x in r.run(["C7", "C9"]).results] == ["SKIPPED", "SKIPPED"]
    assert r.fake_robot.writes == [5]
    assert r.fake_robot.closed


@pytest.mark.parametrize("operation", ["connect", "read_status"])
def test_modbus_error_is_fail_and_closes(make_runner, operation):
    r = make_runner()
    def fail():
        raise RuntimeError("sensitive details must not be serialized")
    setattr(r.fake_robot, operation, fail)
    result = r.run(["C6"]).results[0]
    assert result.status == "FAIL"
    assert result.observed["error_type"] == "RuntimeError"
    assert result.observed["failure_stage"] == ("modbus_connect" if operation == "connect" else "modbus_read")
    assert r.fake_robot.closed
    assert not r.fake_robot.writes
    assert "sensitive" not in str(result)


def test_absent_camera_fails_without_crash_and_closes(make_runner):
    class Missing(Camera):
        def open(self):
            raise RuntimeError("camera absent")
    missing = Missing(None)
    r = make_runner(camera_factory=lambda _: missing)
    assert r.run(["C1"]).results[0].status == "FAIL"
    assert missing.closed


@pytest.mark.parametrize("step", [f"C{i}" for i in range(10, 15)])
def test_unimplemented_physical_steps_stay_blocked_even_with_motion(make_runner, step):
    r = make_runner(allow_motion=True)
    assert r.run([step]).results[0].status == "BLOCKED"
    assert not r.fake_robot.writes
    assert not r.fake_cameras


def test_json_report_is_valid_and_has_safe_configuration(make_runner, tmp_path):
    r = make_runner()
    report = r.run(["C0", "C6", "C10"])
    path = report.save(tmp_path, True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.name.startswith("commissioning_")
    assert path.with_suffix(".txt").is_file()
    assert data["software_commit_sha"]
    assert data["timestamp"]
    assert [item["status"] for item in data["results"]] == ["PASS", "PASS", "BLOCKED"]
    assert "vision_config_path" not in data["configuration"]
    assert "pc_ip" not in data["configuration"]
    assert all(item["duration_seconds"] >= 0 for item in data["results"])


def test_missing_id18_is_explicit_fail(make_runner):
    r = make_runner()
    r.fake_visible.remove(18)
    result = r.run(["C2"]).results[0]
    assert result.status == "FAIL"
    assert result.observed["id18_visibility_percent"] == 0


def test_unknown_software_tests_are_not_claimed_pass(make_runner):
    r = make_runner(test_evidence=None)
    assert r.run(["C0"]).results[0].status == "BLOCKED"


def test_no_occlusion_evidence_is_blocked(make_runner):
    r = make_runner(ask=lambda _: "YES")
    assert r.run(["C5"]).results[0].status == "BLOCKED"


def test_persistent_false_occupancy_is_fail(make_runner):
    r = make_runner()
    def ask(message):
        if "Tras responder" in message:
            r.fake_visible.remove(14)
        return "YES"
    r.ask = ask
    assert r.run(["C5"]).results[0].status == "FAIL"


@pytest.mark.parametrize("statuses", [(0, 2), (0, 1, 3), (0, 1, 2, 0)])
def test_invalid_handshake_stops_session_without_reset(make_runner, statuses):
    r = make_runner(allow_motion=True)
    sequence = iter(statuses)
    r.fake_robot.read_status = lambda: next(sequence)
    assert [x.status for x in r.run(["C7", "C9"]).results] == ["FAIL", "SKIPPED"]
    assert r.fake_robot.writes == [5]
    assert r.fake_robot.closed


def test_timeout_is_fail_and_no_next_command(make_runner):
    r = make_runner(allow_motion=True)
    r.fake_robot.read_status = lambda: 0
    assert [x.status for x in r.run(["C7", "C9"]).results] == ["FAIL", "SKIPPED"]
    assert r.report.results[0].observed["error_type"] == "TimeoutError"
    assert r.fake_robot.writes == [5]


def test_negative_cell_position_is_fail(make_runner):
    r = make_runner(["YES", "YES", "no"], allow_motion=True)
    assert r.run(["C8"]).results[0].status == "FAIL"
    assert r.fake_robot.writes == [5, 0]


def test_cli_configuration_failure_still_writes_report(tmp_path):
    assert cli.main(["--config", str(tmp_path / "missing.yaml"), "--reports-dir", str(tmp_path)]) == 1
    data = json.loads(next(tmp_path.glob("commissioning_*.json")).read_text())
    assert data["results"][0]["status"] == "FAIL"


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_cli_rejects_unbounded_durations(value):
    with pytest.raises(SystemExit):
        cli.main(["--window", value])
