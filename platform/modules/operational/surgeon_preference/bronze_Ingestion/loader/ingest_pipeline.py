from __future__ import annotations

import argparse
import logging
from pathlib import Path

from config.logging_config import configure_logging
from config.settings import load_settings
from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


def main() -> None:
    settings = load_settings()
    configure_logging(settings.project_root / "logs", logging.INFO)

    parser = argparse.ArgumentParser(
        description="Compatibility CLI for the MinIO-backed surgeon preference pipeline."
    )
    parser.add_argument(
        "--source",
        default=str(settings.default_input_path),
        help="Input file or directory to land into MinIO.",
    )
    args = parser.parse_args()

    pipeline = MinIOMedallionPipeline(settings)
    pipeline.run(Path(args.source))


if __name__ == "__main__":
    main()
