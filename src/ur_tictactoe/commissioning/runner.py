"""Injectable lifecycle, abort gates and bounded physical observations."""

from dataclasses import asdict
from contextlib import contextmanager
import math
import time

from ur_tictactoe.communication import ModbusClient
from ur_tictactoe.config import CELL_IDS
from ur_tictactoe.vision.aruco import ArucoDetector
from ur_tictactoe.vision.board_observer import BoardObserver
from ur_tictactoe.vision.camera import Camera
from .report import Report, Result


class Aborted(Exception):
    """No further I/O may be issued in this session."""


class Blocked(Exception):
    """A required operator/configuration prerequisite is absent."""


class Runner:
    def __init__(
        self, app_config, vision_config, *, allow_motion=False, window=10.0,
        timeout=15.0, hold=1.0, ask=input, emit=print,
        clock=time.monotonic, sleep=time.sleep, camera_factory=Camera,
        detector_factory=ArucoDetector, observer_factory=BoardObserver,
        modbus_factory=ModbusClient, test_evidence=None,
    ):
        if any(not math.isfinite(v) or v <= 0 for v in (window, timeout, hold)):
            raise ValueError("Durations must be finite and positive")
        self.app_config, self.vision_config = app_config, vision_config
        self.allow_motion = allow_motion
        self.window, self.timeout, self.hold = window, timeout, hold
        self.ask, self.emit, self.clock, self.sleep = ask, emit, clock, sleep
        self.camera_factory, self.detector_factory = camera_factory, detector_factory
        self.observer_factory, self.modbus_factory = observer_factory, modbus_factory
        self.test_evidence = test_evidence
        self.aborted = False
        self.current_observed = {}
        self.current_comments = []
        self.report = Report({
            "camera": asdict(vision_config.camera),
            "aruco_dictionary": vision_config.aruco.dictionary,
            "cell_ids": list(CELL_IDS), "aruco_profile": "robust",
            "observer": asdict(vision_config.observer),
            "robot_host": app_config.robot_host, "robot_port": app_config.robot_port,
            "allow_motion": allow_motion, "window_seconds": window,
            "timeout_seconds": timeout, "done_hold_seconds": hold,
        })

    def check_abort(self):
        if self.aborted:
            raise Aborted()

    @contextmanager
    def stage(self, name):
        """Record only a fixed internal stage label, never exception text."""
        try:
            yield
        except Exception:
            self.current_observed.setdefault("failure_stage", name)
            raise

    def confirm(self, message):
        self.check_abort()
        try:
            answer = self.ask(message + " [YES/no/ABORT]: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.aborted = True
            raise Aborted() from None
        if answer.upper() in ("ABORT", "ABORTAR", "Q"):
            self.aborted = True
            raise Aborted()
        self.current_comments.append(f"{message}: {'YES' if answer.upper() == 'YES' else 'NO'}")
        return answer.upper() == "YES"

    def require_confirmation(self, message):
        if not self.confirm(message):
            raise Blocked("Operador no confirmó; no se envió el comando siguiente")

    def motion_gate(self):
        self.check_abort()
        if not self.allow_motion:
            raise Blocked("Requiere --allow-motion y confirmación interactiva")

    def connect(self):
        self.check_abort()
        if not self.app_config.robot_host:
            raise Blocked("Host del robot no configurado")
        with self.stage("modbus_connect"):
            client = self.modbus_factory(
                self.app_config.robot_host, port=self.app_config.robot_port,
            )
        try:
            with self.stage("modbus_connect"):
                client.connect()
        except BaseException:
            client.close()
            raise
        return client

    @contextmanager
    def opened_camera(self):
        """Shared lifecycle using the production Camera, with safe error stages."""
        self.check_abort()
        with self.stage("camera_open"):
            camera = self.camera_factory(self.vision_config.camera)
        try:
            with self.stage("camera_open"):
                camera.open()
            with self.stage("camera_settings"):
                settings = asdict(camera.effective_settings)
            yield camera, settings
        finally:
            with self.stage("camera_close"):
                camera.close()

    def sample_camera(self):
        """C1: acquire frames only; no detector, observer or board requirement.

        Every read must succeed. Acquisition timing starts after open/settings;
        the Result duration still includes camera startup and cleanup.
        """
        config = self.vision_config.camera
        values = self.current_observed
        values.update(camera_index=config.index, backend=config.backend,
                      configured_fps=config.fps, frames=0, elapsed_seconds=0.0,
                      measured_fps=0.0)
        with self.opened_camera() as (camera, settings):
            values.update(resolution=[settings["width"], settings["height"]],
                          camera_fps=settings["fps"])
            started = self.clock()
            try:
                while self.clock() - started < self.window:
                    self.check_abort()
                    with self.stage("camera_read"):
                        frame = camera.read()
                        if frame is None or getattr(frame, "size", 1) == 0:
                            raise RuntimeError("Invalid camera frame")
                    values["frames"] += 1
                    self.sleep(0.001)
                with self.stage("camera_read"):
                    if not values["frames"]:
                        raise RuntimeError("No frames captured")
            finally:
                values["elapsed_seconds"] = self.clock() - started
                if values["elapsed_seconds"] > 0:
                    values["measured_fps"] = values["frames"] / values["elapsed_seconds"]
        return values

    def sample(self, *, observer=None, seconds=None):
        self.check_abort()
        with self.stage("observer"):
            observer = observer or self.observer_factory(self.vision_config.observer)
        with self.stage("aruco_detection"):
            detector = self.detector_factory(self.vision_config.aruco.dictionary, "robust")
        counts = dict.fromkeys(CELL_IDS, 0)
        frames = 0
        started = self.clock()
        with self.opened_camera() as (camera, settings):
            duration = self.window if seconds is None else seconds
            while self.clock() - started < duration:
                self.check_abort()
                with self.stage("camera_read"):
                    frame = camera.read()
                with self.stage("aruco_detection"):
                    visible = detector.detect(frame).id_set.intersection(CELL_IDS)
                with self.stage("observer"):
                    observer.update(visible, timestamp=self.clock())
                for marker in visible:
                    counts[marker] += 1
                frames += 1
                self.sleep(0.01)
            if not frames:
                raise RuntimeError("No frames captured")
            elapsed = self.clock() - started
            return observer, {
                "resolution": [settings["width"], settings["height"]],
                "configured_fps": self.vision_config.camera.fps,
                "camera_fps": settings["fps"], "measured_fps": frames / elapsed,
                "profile": "robust", "frames": frames,
                "visible_ids": [marker for marker, count in counts.items() if count],
                "visibility_percent": {str(k): v * 100 / frames for k, v in counts.items()},
                "id18_visibility_percent": counts[18] * 100 / frames,
                "board_ready": observer.state.ready,
                "cells": {str(k): v.value for k, v in observer.state.cells.items()},
            }

    def run(self, selected):
        from .tests import STEPS
        for name in selected:
            if self.aborted:
                self.report.results.append(Result(name, "SKIPPED", comments=["Sesión abortada"]))
                continue
            started = self.clock()
            self.current_observed, self.current_comments = {}, []
            self.emit(f"\n{name} — {STEPS[name][0]}")
            status = "PASS"
            try:
                STEPS[name][1](self)
            except Blocked as exc:
                status = "BLOCKED"
                self.current_comments.append(str(exc))
            except (Aborted, KeyboardInterrupt, EOFError):
                self.aborted = True
                status = "SKIPPED"
                self.current_comments.append(
                    "ABORT: no más comandos. Use la parada física del robot si hay movimiento."
                )
            except Exception as exc:
                status = "FAIL"
                # Do not serialize arbitrary exception messages (paths/credentials).
                self.current_observed["error_type"] = type(exc).__name__
                if name in ("C7", "C8", "C9"):
                    self.aborted = True
                    self.current_comments.append(
                        "Fallo de ensayo de movimiento: sesión detenida; inspeccione el robot "
                        "y COMMAND manualmente. No se reintenta ni se envía reset automático."
                    )
            result = Result(name, status, self.clock() - started,
                            self.current_observed, self.current_comments)
            self.report.results.append(result)
            self.emit(f"{name}: {status}")
        return self.report
