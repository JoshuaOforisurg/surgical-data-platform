from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.logging_config import configure_logging
from config.settings import load_settings


def main() -> None:
    settings = load_settings()
    logger = configure_logging(settings.project_root / "logs", logging.INFO)

    parser = argparse.ArgumentParser(
        description="Run the production surgeon preference medallion pipeline."
    )
    parser.add_argument(
        "--source",
        default=str(settings.default_input_path),
        help="Input file or directory to land into object storage before processing.",
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
    parser.add_argument(
        "--synthetic-output-mode",
        choices=["master", "partitioned", "both"],
        default=settings.synthetic_output_mode,
        help="master writes aggregate files; partitioned writes one structured source file per card.",
    )
    parser.add_argument(
        "--synthetic-file-formats",
        default=settings.synthetic_file_formats,
        help="Comma-separated partitioned formats. Structured ingestion supports json,csv.",
    )
    parser.add_argument(
        "--check-postgres",
        action="store_true",
        help="Initialise and validate the Postgres metadata catalogue, then exit.",
    )
    args = parser.parse_args()

    if args.check_postgres:
        report = BronzeCatalogRepository(settings.postgres).healthcheck(initialise=True)
        print(json.dumps(report, indent=2))
        if not report["valid"]:
            raise SystemExit(1)
        return

    source_path = Path(args.source)
    if source_path == settings.default_input_path and not args.use_existing_synthetic:
        from generate_synthetic_data.main_synthetic_generator import generate_batch

        logger.info(
            "Generating %s clinically aligned synthetic preference cards mode=%s formats=%s.",
            args.synthetic_count,
            args.synthetic_output_mode,
            args.synthetic_file_formats,
        )
        generate_batch(
            n=args.synthetic_count,
            output_dir=str(source_path.parent),
            messy=True,
            output_mode=args.synthetic_output_mode,
            file_formats=args.synthetic_file_formats,
        )
        if args.synthetic_output_mode == "partitioned":
            source_path = source_path.parent / "partitioned"

    from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline

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
