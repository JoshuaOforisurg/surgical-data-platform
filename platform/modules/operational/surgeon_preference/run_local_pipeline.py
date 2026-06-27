from __future__ import annotations

import logging
from pathlib import Path

from config.logging_config import configure_logging
from config.settings import load_settings
from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


def main() -> None:
    settings = load_settings()
    configure_logging(settings.project_root / "logs", logging.INFO)

    pipeline = MinIOMedallionPipeline(settings)
    result = pipeline.run(Path(settings.default_input_path))

    print("\nLOCAL PIPELINE COMPLETE")
    print(f"Run ID: {result['run_id']}")
    print(f"Files landed: {result['files_landed']}")
    print(f"Records processed: {result['records_processed']}")
    print(f"Gold CSV key: {result['gold_keys']['operational_latest_csv']}")


if __name__ == "__main__":
    main()
