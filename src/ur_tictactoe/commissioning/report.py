"""Session reports with an explicit, non-sensitive configuration allowlist."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


@dataclass
class Result:
    test: str
    status: str
    duration_seconds: float = 0.0
    observed: dict = field(default_factory=dict)
    comments: list[str] = field(default_factory=list)


def software_sha() -> str:
    root = Path(__file__).resolve().parents[3]
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


class Report:
    def __init__(self, configuration: dict, sha: str | None = None):
        self.timestamp = datetime.now(timezone.utc)
        self.sha = sha or software_sha()
        self.configuration = configuration
        self.results: list[Result] = []

    def save(self, directory: Path, text_report: bool = False) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"commissioning_{self.timestamp:%Y%m%dT%H%M%S_%fZ}.json"
        data = {
            "timestamp": self.timestamp.isoformat(), "software_commit_sha": self.sha,
            "configuration": self.configuration,
            "results": [asdict(result) for result in self.results],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if text_report:
            path.with_suffix(".txt").write_text(
                f"Robot Triqui Commissioning\n{data['timestamp']}\nSHA: {self.sha}\n"
                + "\n".join(
                    f"{r.test}: {r.status} ({r.duration_seconds:.3f}s) "
                    f"{json.dumps(r.observed, ensure_ascii=False)} {'; '.join(r.comments)}"
                    for r in self.results
                ) + "\n", encoding="utf-8",
            )
        return path
