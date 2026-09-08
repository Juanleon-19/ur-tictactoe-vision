"""Run with python -m ur_tictactoe.commissioning (src on PYTHONPATH)."""

import argparse
import math
from pathlib import Path

from ur_tictactoe.config import load_vision_config
from ur_tictactoe.desktop.settings import load_app_config
from .report import Report, Result
from .runner import Runner
from .tests import STEPS


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be finite and positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Robot Triqui Commissioning / HIL Acceptance Runner")
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS)[:7])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--window", type=positive, default=10.0)
    parser.add_argument("--timeout", type=positive, default=15.0)
    parser.add_argument("--done-hold", type=positive, default=1.0)
    parser.add_argument("--allow-motion", action="store_true")
    parser.add_argument("--pytest-report", type=Path, help="JUnit XML de esta versión; nunca ejecuta pytest/hardware")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--text-report", action="store_true")
    args = parser.parse_args(argv)
    report = Report({"configuration_loaded": False})
    try:
        config = load_app_config(args.config)
        vision = load_vision_config(config.vision_config_path)
        runner = Runner(config, vision, allow_motion=args.allow_motion, window=args.window,
                        timeout=args.timeout, hold=args.done_hold, test_evidence=args.pytest_report)
        print("Por defecto READ ONLY. YES confirma; ABORT o Ctrl+C detiene nuevas acciones.")
        print("ABORT no es una parada física. Ante movimiento, use la parada del robot.")
        print("No escriba secretos ni datos personales en comentarios/configuración de sesión.")
        report = runner.run(args.steps)
    except Exception as exc:
        report.results.append(Result("C0", "FAIL", observed={"error_type": type(exc).__name__}))
    finally:
        path = report.save(args.reports_dir, args.text_report)
        print(f"Reporte: {path}")
    return 0 if all(r.status == "PASS" for r in report.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
