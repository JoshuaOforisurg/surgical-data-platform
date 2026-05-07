import logging
from datetime import datetime

from ingest import ingest_data
from transform import transform_preference_data
from validate import validate_dataframe
from load import load_to_postgres

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_pipeline(
    source_path: str,
    schema: str = "staging",
    table: str = "surgeon_preferences",
    source_type: str = "csv"
):
    logger.info("🚀 Surgeon Preference Pipeline started")
    start_time = datetime.now()

    # 1. Ingest
    logger.info("📥 Ingesting data...")
    df = ingest_data(source_path)
    logger.info(f"Ingested {len(df)} rows")

    # 2. Transform
    logger.info(" Transforming data...")
    df = transform_preference_data(df, source=source_type)

    # 3. Validate
    logger.info(" Validating data...")
    report = validate_dataframe(df)

    if report["status"] != "PASS":
        logger.error(" Validation failed")
        logger.error(report["errors"])
        return

    logger.info(" Validation passed")

    # 4. Load
    logger.info(f"Loading into {schema}.{table}...")
    load_to_postgres(df, schema=schema, table=table)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info(f"🎉 Pipeline completed in {duration} seconds")


if __name__ == "__main__":
    run_pipeline("data/raw/surgeon_preferences.csv")
