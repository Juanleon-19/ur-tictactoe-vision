"""Read-only, validated view of the latest local commissioning report."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CommissioningStatus:
    source: str
    results: dict[str, str]


def latest_commissioning(directory: Path) -> CommissioningStatus | None:
    try:
        paths = sorted(directory.glob("commissioning_*.json"),
                       key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
    except OSError:
        return None
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
            return CommissioningStatus(path.name, results)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue
    return None
