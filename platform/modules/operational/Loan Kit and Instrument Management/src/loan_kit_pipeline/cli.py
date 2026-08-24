from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process loan-kit workflow evidence.")
    parser.add_argument("--input", required=True, type=Path, help="Source workflow-event CSV")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--minimum-lead-days", type=int, default=14)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_pipeline(args.input, args.output, args.minimum_lead_days)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "completed", **summary}, sort_keys=True))
    return 0
