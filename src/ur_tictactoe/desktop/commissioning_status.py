"""Read-only, validated view of the latest local commissioning report."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(frozen=True)
class CommissioningStatus:
    source: str
    results: dict[str, str]
    timestamp: str = "No disponible"
    software_commit_sha: str = "No disponible"
    order_time: float = 0.0


def valid_reports(directory: Path) -> list[CommissioningStatus]:
    try:
        paths = sorted(directory.glob("commissioning_*.json"),
                       key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
    except OSError:
        return []
    reports = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data["results"]
            if not isinstance(rows, list) or not rows:
                continue
            results = {}
            for row in rows:
                step, status = row["test"], row["status"]
                if step not in {f"C{i}" for i in range(15)} or status not in {
                    "PASS", "FAIL", "BLOCKED", "SKIPPED"
                } or step in results:
                    raise ValueError("Invalid result")
                results[step] = status
            timestamp = data.get("timestamp", "No disponible")
            sha = data.get("software_commit_sha", "No disponible")
            if not isinstance(timestamp, str) or not isinstance(sha, str):
                raise ValueError("Invalid metadata")
            order_time = path.stat().st_mtime
            if timestamp != "No disponible":
                date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                order_time = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
            reports.append(CommissioningStatus(path.name, results, timestamp, sha, order_time))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue
    return reports


def latest_commissioning(directory: Path) -> CommissioningStatus | None:
    """Retain latest-session selection by file modification time."""
    reports = valid_reports(directory)
    return reports[0] if reports else None


def validation_history(directory: Path) -> dict[str, CommissioningStatus]:
    """Latest explicit result per step, ordered by report timestamp (mtime fallback)."""
    history = {}
    for report in sorted(valid_reports(directory), key=lambda r: (r.order_time, r.source), reverse=True):
        for step in report.results:
            history.setdefault(step, report)
    return history


def next_operational_step(history: dict[str, CommissioningStatus]) -> str | None:
    # C0 is software evidence, separate from the physical operational sequence.
    return next((f"C{i}" for i in range(1, 15)
                 if f"C{i}" not in history or history[f"C{i}"].results[f"C{i}"] != "PASS"), None)
