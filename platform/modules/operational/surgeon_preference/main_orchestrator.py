from __future__ import annotations

import argparse
import logging
from pathlib import Path

from config.logging_config import configure_logging
from config.settings import load_settings
from generate_synthetic_data.main_synthetic_generator import generate_batch
from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


def main() -> None:
    settings = load_settings()
    logger = configure_logging(settings.project_root / "logs", logging.INFO)

    parser = argparse.ArgumentParser(
        description="Run the production surgeon preference MinIO medallion pipeline."
    )
    parser.add_argument(
        "--source",
        default=str(settings.default_input_path),
        help="Input file or directory to land into MinIO before processing.",
    )
    parser.add_argument(
        "--synthetic-count",
        type=int,
        default=settings.synthetic_record_count,
        help="Number of synthetic cards to generate when using the default source path.",
    )
    parser.add_argument(
        "--use-existing-synthetic",
        action="store_true",
        help="Use the existing default synthetic file instead of regenerating it.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if source_path == settings.default_input_path and not args.use_existing_synthetic:
        logger.info(
            "Generating %s clinically aligned synthetic preference cards.",
            args.synthetic_count,
        )
        generate_batch(n=args.synthetic_count, output_dir=str(source_path.parent), messy=True)

    pipeline = MinIOMedallionPipeline(settings)
    result = pipeline.run(source_path)

    logger.info(
        "Run complete | run_id=%s | files=%s | records=%s | gold_key=%s",
        result["run_id"],
        result["files_landed"],
        result["records_processed"],
        result["gold_keys"]["operational_latest_csv"],
    )


if __name__ == "__main__":
    main()
