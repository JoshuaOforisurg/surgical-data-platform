from __future__ import annotations

from pathlib import Path

from config.settings import load_settings
from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


def run_pipeline(source_path: str | None = None) -> dict:
    """
    Backwards-compatible entry point.

    The supported pipeline now lands source files in MinIO, registers bronze
    metadata in Postgres, transforms to silver/gold, and publishes gold back to
    MinIO for Streamlit.
    """
    settings = load_settings()
    pipeline = MinIOMedallionPipeline(settings)
    return pipeline.run(Path(source_path) if source_path else settings.default_input_path)


if __name__ == "__main__":
    run_pipeline()
