import os
import argparse
from pathlib import Path
from typing import Type, Any

from extractors.extractor_interface import BaseExtractor
from extractors.csv_extractor import CSVExtractor
from extractors.json_extractor import JsonExtractor
from extractors.pdf_extractor import PdfExtractor
from extractors.txt_extractor import TXTExtractor

from normalization.normalization_layer import NormalisedPreferenceItem
from normalization.lookup_table import DynamicMapper

from quarantine.quarantine_handler import QuarantineHandler
from loader.database_loader import PostgresLoader


EXTRACTOR_REGISTRY: dict[str, Type[BaseExtractor]] = {
    ".csv": CSVExtractor,
    ".json": JsonExtractor,
    ".txt": TXTExtractor,
    ".pdf": PdfExtractor,
}


def get_extractor(source: str) -> BaseExtractor:
    ext = Path(source).suffix.lower()

    if ext not in EXTRACTOR_REGISTRY:
        raise ValueError(f"Unsupported file type: {ext}")

    return EXTRACTOR_REGISTRY[ext](source)


from datetime import datetime


def ingest_source(
        source: str,
        conn_string: str,
        target_table: str = "bronze_raw.surgeon_preference_items",  # Pass target table dynamically
        quarantine_dir: str = "quarantine",
        batch_size: int = 500,
) -> None:
    if not conn_string or conn_string.strip() == "":
        raise ValueError("Invalid Postgres connection string")

    quarantine = QuarantineHandler(output_dir=quarantine_dir)
    loader = PostgresLoader(conn_string=conn_string, batch_size=batch_size)

    # Initialize the dynamic database mapper
    mapper = DynamicMapper(conn_string, target_table)

    meta: dict[str, Any] = {}

    try:
        with get_extractor(source) as extractor:
            for raw in extractor.extract():
                try:
                    # 1. DYNAMIC LOOKUP / TRANSFORM STEP
                    transformed = mapper.transform_row(raw)

                    # 2. SYSTEM INJECTED FIELDS

                    transformed["source_file"] = str(source)
                    transformed["ingested_at"] = datetime.now().isoformat()

                    # 3. VALIDATION STEP
                    # Note: If your Pydantic model is strict, you can pass transformed fields directly
                    validated = NormalisedPreferenceItem(**transformed)

                    # 4. LOAD STEP
                    loader.add(
                        validated.model_dump(),
                        source_file=str(source),
                    )
                except Exception as e:
                    quarantine.add(raw_row=raw, error=str(e), source=str(source))

            meta = extractor.metadata()

        loader.close()
        quarantine.flush()
        print("Ingestion complete", meta)

    except Exception as e:
        loader.close()
        raise RuntimeError(f"Ingestion pipeline failed: {e}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--conn-string", default=os.getenv(".env"))

    args = parser.parse_args()

    ingest_source(
        source=args.source,
        conn_string=args.conn_string,
    )

