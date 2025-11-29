"""Command line entrypoint for the DJ identifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from .metadata import FingerprintStore
from .pipeline import bootstrap_store, run_pipeline


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Segment a DJ set and identify tracks.")
    parser.add_argument("audio", help="Path to the DJ set audio file")
    parser.add_argument(
        "--fingerprints",
        type=Path,
        default=Path("fingerprints.json"),
        help="JSON file containing known track fingerprints",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=None,
        help="Optional limit on the number of detected segments",
    )
    parser.add_argument(
        "--min-segment-duration",
        type=float,
        default=1.0,
        help="Merge or skip segments shorter than this duration (seconds)",
    )
    parser.add_argument(
        "--bootstrap",
        type=Path,
        default=None,
        help="Optional JSON file with sample fingerprints to seed the store",
    )
    return parser.parse_args(argv)


def load_bootstrap(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)

    bootstrap_data = load_bootstrap(args.bootstrap)
    store = bootstrap_store(bootstrap_data, path=args.fingerprints)

    matches = run_pipeline(
        args.audio,
        store,
        max_segments=args.max_segments,
        min_segment_duration=args.min_segment_duration,
    )
    for match in matches:
        print(
            f"{match.segment.start:7.2f}-{match.segment.end:7.2f} "
            f"| {match.title} — {match.artist} (score={match.confidence:.2f})"
        )


if __name__ == "__main__":
    main()
