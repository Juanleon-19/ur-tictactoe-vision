"""Evidence is read-only and never promotes missing or unsuccessful results."""

import json
import os

from ur_tictactoe.desktop.commissioning_status import (
    latest_commissioning, validation_history, next_operational_step,
)
from ur_tictactoe.desktop.help_content import report_text
from ur_tictactoe.desktop.operator_guidance import procedure
from ur_tictactoe.desktop.operator_style import STATUS_COLORS
from ur_tictactoe.desktop import theme


def report(directory, name, timestamp, results, modified):
    path = directory / f"commissioning_{name}.json"
    path.write_text(json.dumps({"timestamp": timestamp, "software_commit_sha": name,
                               "results": [{"test": step, "status": status}
                                           for step, status in results.items()]}), encoding="utf-8")
    os.utime(path, (modified, modified))
    return path


def test_session_and_history_preserve_provenance(tmp_path):
    first = report(tmp_path, "sha1", "2026-09-01T10:00:00Z", {"C1": "PASS", "C2": "PASS", "C3": "PASS"}, 20)
    last = report(tmp_path, "sha2", "2026-09-02T10:00:00+00:00", {"C4": "PASS"}, 30)
    before = {p: p.read_bytes() for p in (first, last)}
    session = latest_commissioning(tmp_path)
    assert session.source == last.name and session.results == {"C4": "PASS"}
    assert "C1 " not in report_text(session)
    assert "sha2" in report_text(session)
    history = validation_history(tmp_path)
    assert set(history) == {"C1", "C2", "C3", "C4"}
    assert history["C1"].timestamp == "2026-09-01T10:00:00Z"
    assert history["C1"].software_commit_sha == "sha1"
    assert history["C4"].software_commit_sha == "sha2"
    assert next_operational_step(history) == "C5"
    report(tmp_path, "sha3", "2026-09-03T10:00:00Z", {"C5": "PASS"}, 40)
    assert next_operational_step(validation_history(tmp_path)) == "C6"
    assert all(path.read_bytes() == data for path, data in before.items())


def test_latest_explicit_failure_overrides_old_pass_and_corrupt_is_ignored(tmp_path):
    report(tmp_path, "old", "2026-09-01T10:00:00Z", {"C1": "PASS", "C2": "PASS"}, 50)
    # History uses event timestamp even if an older file was copied more recently.
    report(tmp_path, "new", "2026-09-02T10:00:00Z", {"C1": "FAIL", "C3": "BLOCKED", "C4": "SKIPPED"}, 40)
    (tmp_path / "commissioning_corrupt.json").write_text("{bad", encoding="utf-8")
    history = validation_history(tmp_path)
    assert {s: r.results[s] for s, r in history.items()} == {
        "C1": "FAIL", "C2": "PASS", "C3": "BLOCKED", "C4": "SKIPPED"}
    assert next_operational_step(history) == "C1"
    assert latest_commissioning(tmp_path).software_commit_sha == "old"
    assert STATUS_COLORS == {"PASS": theme.SUCCESS, "FAIL": theme.ERROR,
                            "BLOCKED": theme.WARNING, "SKIPPED": theme.DISABLED,
                            "PENDIENTE": theme.DISABLED}


def test_empty_history_and_procedures(tmp_path):
    assert validation_history(tmp_path) == {}
    assert next_operational_step({}) == "C1"
    for i in range(1, 15):
        content = procedure(f"C{i}")
        assert set(content) == {"Objetivo", "Preparación", "Qué observar", "Criterio general", "Nivel de riesgo"}
        assert all(content.values())
        risk = content["Nivel de riesgo"]
        assert risk == ("SIN MOVIMIENTO" if i <= 6 else "HANDSHAKE SIN MOVIMIENTO ESPERADO"
                        if i == 7 else "MOVIMIENTO FÍSICO" if i in (8, 9, 12, 13)
                        else "EVIDENCIA MANUAL / SIN I/O" if i in (10, 11)
                        else "PRECONDICIONES / PENDIENTE")
    assert "sin reiniciar el observer" in procedure("C5")["Qué observar"]
