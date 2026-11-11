from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .medallion import LoanKitMedallionPipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the V0.2 loan-kit operational pipeline.")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 evaluation time")
    args = parser.parse_args(argv)
    try:
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        result = LoanKitMedallionPipeline().run(args.source_dir, args.output, as_of)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "completed", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
