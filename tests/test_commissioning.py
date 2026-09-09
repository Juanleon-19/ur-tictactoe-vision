"""Acceptance of the harness with no sockets, camera or robot."""

import json
from dataclasses import replace
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
        self.open_count = self.close_count = self.read_count = 0
        self.effective_settings = CameraSettings(640, 480, 30)

    def open(self):
        self.open_count += 1

    def read(self):
        self.read_count += 1
        return object()

    def close(self):
        self.close_count += 1
        self.closed = True


class FakePreview:
    closed = False

    def __init__(self, profile="robust"):
        self.profile = profile

    def poll_key(self):
        return -1

    def __enter__(self):
        return self

    def show(self, frame, detection, fps):
        return ord("c")

    def __exit__(self, *args):
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
            preview_factory=FakePreview,
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


def test_c2_slow_camera_open_does_not_consume_capture_window(make_runner):
    r = make_runner(window=1)
    camera = Camera(None)
    camera.open = lambda: r.sleep(60)
    r.camera_factory = lambda _: camera
    result = r.run(["C2"]).results[0]
    assert result.status == "PASS", result
    assert result.duration_seconds >= 61
    assert 1 <= result.observed["capture_elapsed_seconds"] < 1.02
    assert result.observed["frames"] >= 100
    assert result.observed["visible_ids"] == list(range(10, 19))
    assert result.observed["id18_visibility_percent"] == 100
    assert camera.closed


def test_c2_preview_time_and_frames_are_excluded_and_camera_is_reused(make_runner):
    r = make_runner(window=1)
    updates = []
    observer = r.observer_factory(r.vision_config.observer)
    original_update = observer.update
    window = FakePreview()
    keys = iter((-1, ord("C")))

    def show(*args):
        assert not updates
        r.sleep(5)
        return next(keys)

    def update(*args, **kwargs):
        assert window.closed
        updates.append(args)
        return original_update(*args, **kwargs)

    window.show = show
    observer.update = update
    r.preview_factory = lambda **kwargs: window
    r.observer_factory = lambda _: observer
    result = r.run(["C2"]).results[0]
    assert result.status == "PASS"
    assert len(r.fake_cameras) == 1
    assert r.fake_cameras[0].closed
    assert 11 <= result.duration_seconds < 11.02
    assert 1 <= result.observed["capture_elapsed_seconds"] < 1.02
    assert result.observed["frames"] == len(updates)
    assert result.observed["measured_fps"] == pytest.approx(
        len(updates) / result.observed["capture_elapsed_seconds"])


@pytest.mark.parametrize("key", [ord("q"), ord("Q"), 27])
def test_c2_preview_cancel_prevents_measurement_and_next_step(make_runner, key):
    r = make_runner()
    reads, detections = [], []
    camera, window = Camera(None), FakePreview()
    camera.read = lambda: reads.append(True) or object()
    window.show = lambda *args: key
    r.camera_factory = lambda _: camera
    r.preview_factory = lambda **kwargs: window
    r.detector_factory = lambda *args: SimpleNamespace(detect=lambda _: detections.append(True) or object())
    r.observer_factory = lambda _: SimpleNamespace(update=lambda *args, **kwargs: pytest.fail("Observer used during preview"))
    results = r.run(["C2", "C3"]).results
    assert [result.status for result in results] == ["SKIPPED", "SKIPPED"]
    assert len(reads) == len(detections) == 1
    assert "frames" not in results[0].observed
    assert window.closed and camera.closed


def test_c2_preview_visibility_does_not_make_measurement_pass(make_runner):
    r = make_runner(window=1)
    detections = []

    def detect(frame):
        detections.append(True)
        return SimpleNamespace(id_set=set(range(10, 19 if len(detections) == 1 else 18)))

    r.detector_factory = lambda *args: SimpleNamespace(detect=detect)
    result = r.run(["C2"]).results[0]
    assert result.status == "FAIL"
    assert result.observed["id18_visibility_percent"] == 0
    assert 18 not in result.observed["visible_ids"]
    assert len(detections) == result.observed["frames"] + 1


@pytest.mark.parametrize("step", ["C2", "C3", "C4", "C5"])
@pytest.mark.parametrize("stage", ["camera_open", "camera_settings", "camera_read"])
def test_vision_steps_preserve_safe_camera_failure_stage(make_runner, step, stage):
    class BrokenCamera:
        closed = False

        def open(self):
            if stage == "camera_open":
                raise RuntimeError("private path")

        @property
        def effective_settings(self):
            if stage == "camera_settings":
                raise RuntimeError("private path")
            return CameraSettings(1280, 720, 30)

        def read(self):
            raise RuntimeError("private path")

        def close(self):
            self.closed = True

    camera = BrokenCamera()
    r = make_runner(camera_factory=lambda _: camera)
    result = r.run([step]).results[0]
    assert result.status == "FAIL"
    assert result.observed["failure_stage"] == stage
    assert "private path" not in str(result)
    assert camera.closed


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


@pytest.mark.parametrize("profile", ["default", "robust", "robust_glare"])
def test_commissioning_uses_selected_profile_for_detector_preview_and_report(make_runner, profile):
    r = make_runner()
    config = replace(r.app_config, aruco_profile=profile)
    r = Runner(config, r.vision_config, clock=r.clock, sleep=r.sleep,
               camera_factory=r.camera_factory, detector_factory=r.detector_factory,
               preview_factory=FakePreview, window=0.1, emit=lambda _: None)
    detector_profiles, preview_profiles = [], []
    factory = r.detector_factory
    def detector(dictionary, selected):
        detector_profiles.append(selected)
        return factory(dictionary, selected)
    def preview(profile):
        preview_profiles.append(profile)
        return FakePreview(profile)
    r.detector_factory, r.preview_factory = detector, preview
    result = r.run(["C2"]).results[0]
    assert result.status == "PASS"
    assert detector_profiles == preview_profiles == [profile]
    assert result.observed["profile"] == profile
    assert r.report.configuration["aruco_profile"] == profile


@pytest.mark.parametrize("override, expected", [([], "default"), (["--aruco-profile", "robust_glare"], "robust_glare")])
def test_cli_profile_override_is_session_only(monkeypatch, tmp_path, override, expected):
    from ur_tictactoe.commissioning.report import Report, Result
    config = tmp_path / "app.yaml"
    content = "aruco_profile: default\n"
    config.write_text(content)
    selected = []
    class FakeRunner:
        def __init__(self, app_config, vision_config, **kwargs):
            selected.append(app_config.aruco_profile)
        def run(self, steps):
            report = Report({"aruco_profile": selected[-1]})
            report.results.append(Result("C2", "PASS"))
            return report
    monkeypatch.setattr(cli, "Runner", FakeRunner)
    assert cli.main(["--config", str(config), "--steps", "C2", "--reports-dir", str(tmp_path), *override]) == 0
    assert selected == [expected]
    assert config.read_text() == content


def test_x_during_detection_cancels_runner_without_measurement(monkeypatch, make_runner):
    from ur_tictactoe.commissioning import preview
    alive, events, reads = [True], [], []
    monkeypatch.setattr(preview.cv2, "namedWindow", lambda *args: events.append("open"))
    monkeypatch.setattr(preview.cv2, "getWindowProperty", lambda *args: 1 if alive[0] else -1)
    monkeypatch.setattr(preview.cv2, "waitKey", lambda _: -1)
    monkeypatch.setattr(preview.cv2, "imshow", lambda *args: pytest.fail("Closed window must not be recreated"))
    monkeypatch.setattr(preview.cv2, "destroyWindow", lambda *args: events.append("destroy"))
    r = make_runner(preview_factory=preview.VisionPreview)
    camera = Camera(None)
    camera.read = lambda: reads.append(True) or object()
    r.camera_factory = lambda _: camera
    def detect(frame):
        alive[0] = False
        return object()
    r.detector_factory = lambda *args: SimpleNamespace(detect=detect)
    r.observer_factory = lambda _: SimpleNamespace(update=lambda *args, **kwargs: pytest.fail("Measurement started after X"))
    results = r.run(["C2", "C3"]).results
    assert [x.status for x in results] == ["SKIPPED", "SKIPPED"]
    assert events == ["open"]
    assert reads == [True]
    assert camera.closed
    assert "frames" not in results[0].observed


@pytest.mark.parametrize("step", ["C1", "C2", "C3", "C4", "C5"])
def test_camera_lifecycle_and_window_counts(make_runner, step):
    r = make_runner()
    result = r.run([step]).results[0]
    assert result.status == "PASS"
    assert len(r.fake_cameras) == 1
    camera = r.fake_cameras[0]
    assert camera.open_count == camera.close_count == 1
    observations = result.observed.get("observations", [result.observed])
    assert len(observations) == (3 if step in ("C4", "C5") else 1)
    measured = sum(item["frames"] for item in observations)
    extra = 9 if step in ("C4", "C5") else (1 if step == "C2" else 0)
    assert camera.read_count == measured + extra


@pytest.mark.parametrize("step", ["C4", "C5"])
@pytest.mark.parametrize("answer, status", [("ABORT", "SKIPPED"), ("no", "BLOCKED")])
@pytest.mark.parametrize("prompt", [2, 3])
def test_shared_camera_closes_at_operator_exit(make_runner, step, answer, status, prompt):
    r = make_runner(["YES"] * (prompt - 1) + [answer])
    results = r.run([step, "C1"]).results
    assert results[0].status == status
    camera = r.fake_cameras[0]
    assert camera.open_count == camera.close_count == 1
    if answer == "ABORT":
        assert results[1].status == "SKIPPED"
        assert len(r.fake_cameras) == 1


@pytest.mark.parametrize("step", ["C4", "C5"])
@pytest.mark.parametrize("stage", ["camera_read", "aruco_detection", "observer"])
def test_shared_camera_closes_on_later_window_exception(make_runner, step, stage):
    r = make_runner()
    ask = r.ask

    def fail(*args, **kwargs):
        raise RuntimeError("private details")

    def confirm(message):
        answer = ask(message)
        if len(r.current_observed.get("observations", [])) == 1:
            if stage == "camera_read":
                r.fake_cameras[0].read = fail
            else:
                setattr(processors[stage], "detect" if stage == "aruco_detection" else "update", fail)
        return answer

    processors = {}
    for attribute, label in (("detector_factory", "aruco_detection"), ("observer_factory", "observer")):
        factory = getattr(r, attribute)
        def track(*args, factory=factory, label=label):
            processors[label] = factory(*args)
            return processors[label]
        setattr(r, attribute, track)
    r.ask = confirm
    result = r.run([step]).results[0]
    assert result.status == "FAIL"
    assert result.observed["failure_stage"] == stage
    assert "private details" not in str(result)
    assert len(r.fake_cameras) == 1
    assert r.fake_cameras[0].open_count == r.fake_cameras[0].close_count == 1


@pytest.mark.parametrize("step", ["C4", "C5"])
def test_shared_windows_keep_processors_and_exclude_stale_frames(make_runner, step):
    r = make_runner()
    observers, detectors, updates, detected = [], [], [], []
    observer_factory, detector_factory = r.observer_factory, r.detector_factory
    camera_factory = r.camera_factory
    flush_reads = []

    def make_observer(config):
        observer = observer_factory(config)
        update = observer.update
        def record(visible, **kwargs):
            updates.append((len(r.current_observed.get("observations", [])), kwargs["timestamp"]))
            return update(visible, **kwargs)
        observer.update = record
        observers.append(observer)
        return observer

    def make_detector(dictionary, profile):
        detector = detector_factory(dictionary, profile)
        detect = detector.detect
        def record(frame):
            assert frame != "stale"
            detected.append(frame)
            return detect(frame)
        detector.detect = record
        detectors.append((dictionary, profile, detector))
        return detector

    def make_camera(config):
        camera = camera_factory(config)
        read = camera.read
        per_window = {}
        def buffered_read():
            frame = read()
            index = len(r.current_observed.get("observations", []))
            per_window[index] = per_window.get(index, 0) + 1
            if per_window[index] <= 3:
                flush_reads.append(index)
                r.sleep(0.02)
                return "stale"
            return frame
        camera.read = buffered_read
        return camera

    r.observer_factory, r.detector_factory, r.camera_factory = make_observer, make_detector, make_camera
    result = r.run([step]).results[0]
    assert result.status == "PASS", result
    assert len(observers) == len(detectors) == 1
    assert detectors[0][:2] == (r.vision_config.aruco.dictionary, r.app_config.aruco_profile)
    assert flush_reads == [0] * 3 + [1] * 3 + [2] * 3
    observations = result.observed["observations"]
    assert len(detected) == len(updates) == sum(item["frames"] for item in observations)
    for index, item in enumerate(observations):
        assert sum(window == index for window, _ in updates) == item["frames"]
        assert r.window <= item["capture_elapsed_seconds"] < r.window + 0.011
        assert item["measured_fps"] == pytest.approx(item["frames"] / item["capture_elapsed_seconds"])
    assert result.duration_seconds == pytest.approx(
        sum(item["capture_elapsed_seconds"] for item in observations) + 0.18)
    if step == "C5":
        assert all(value == "FREE" for value in observations[2]["cells"].values())
        assert any(value < 100 for value in observations[1]["visibility_percent"].values())


@pytest.mark.parametrize("prompt", [1, 2, 3])
def test_c4_rejects_wrong_occupancy_at_each_window(make_runner, prompt):
    r = make_runner()
    ask, calls = r.ask, []
    def wrong_board(message):
        answer = ask(message)
        calls.append(message)
        if len(calls) == prompt:
            r.fake_visible.discard(11)  # Unexpected occupied CELL2.
        return answer
    r.ask = wrong_board
    result = r.run(["C4"]).results[0]
    assert result.status == "FAIL"
    assert len(result.observed["observations"]) == prompt
    assert r.fake_cameras[0].open_count == r.fake_cameras[0].close_count == 1


@pytest.mark.parametrize("missing", [{14}, set(range(10, 19))])
def test_c5_recovery_must_be_empty_and_ready(make_runner, missing):
    r = make_runner()
    def emit(message):
        if message.startswith("Recuperaci"):
            r.fake_visible.difference_update(missing)
    r.emit = emit
    result = r.run(["C5"]).results[0]
    assert result.status == "FAIL"
    assert len(result.observed["observations"]) == 3
    assert any(value != "FREE" for value in result.observed["observations"][-1]["cells"].values())
    assert r.fake_cameras[0].open_count == r.fake_cameras[0].close_count == 1
