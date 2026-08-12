from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ur_tictactoe.config import ArucoConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate printable ArUco marker PNG files")
    parser.add_argument("--dictionary", default="DICT_5X5_50")
    parser.add_argument("--ids", nargs="+", type=int, default=list(ArucoConfig().all_ids))
    parser.add_argument("--pixels", type=int, default=600)
    parser.add_argument("--output", type=Path, default=Path("assets/aruco"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not hasattr(cv2.aruco, args.dictionary):
        raise ValueError(f"Unknown ArUco dictionary: {args.dictionary}")
    if args.pixels <= 0:
        raise ValueError("--pixels must be positive")

    dictionary_id = getattr(cv2.aruco, args.dictionary)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    marker_count = dictionary.bytesList.shape[0]
    invalid_ids = sorted({marker_id for marker_id in args.ids if not 0 <= marker_id < marker_count})
    if invalid_ids:
        raise ValueError(
            f"Marker IDs {invalid_ids} are invalid for {args.dictionary}; "
            f"valid IDs are 0 through {marker_count - 1}."
        )
    args.output.mkdir(parents=True, exist_ok=True)

    for marker_id in args.ids:
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, args.pixels)
        output_path = args.output / f"aruco_{args.dictionary}_{marker_id}.png"
        if not cv2.imwrite(str(output_path), marker):
            raise RuntimeError(f"Could not write marker image: {output_path}")
        print(f"Generated {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
