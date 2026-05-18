import os
import argparse
from pathlib import Path
from typing import Type, Any

# --- Import Extractors Safely (Matching exact casing) ---
from extractors.extractor_interface import BaseExtractor
from extractors.csv_extractor import CSVExtractor
from extractors.json_extractor import JsonExtractor  # Casing fixed
from extractors.pdf_extractor import PdfExtractor    # Casing fixed
from extractors.txt_extractor import TXTExtractor    # Added missing import

# --- Import Normalisation, Quarantine, and Load Layers ---
from normalization.normalization_layer import NormalisedPreferenceItem  # Added missing function import
from quarantine.quarantine_handler import QuarantineHandler
from loader.database_loader import PostgresLoader


# --- extractor registry -----------------------------------------------------


EXTRACTOR_REGISTRY: dict[str, Type[BaseExtractor]] = {
    ".csv": CSVExtractor,
    ".json": JsonExtractor,  # FIXED: Matches import casing
    ".txt": TXTExtractor,    # FIXED: Now imported at top
    ".pdf": PdfExtractor,    # FIXED: Matches import casing
}


def get_extractor_for_source(source: str) -> BaseExtractor:
    path = Path(source)
    ext = path.suffix.lower()

    extractor_cls = EXTRACTOR_REGISTRY.get(ext)
    if extractor_cls is None:
        raise ValueError(f"No extractor registered for extension: {ext}")

    return extractor_cls(source)


# --- core ingestion function -----------------------------------------------

def ingest_source(
    source: str,
    conn_string: str,
    quarantine_dir: str = "quarantine",
    batch_size: int = 500,
) -> None:
    """
    End-to-end ingestion for a single source (file/API/etc.).
    """
    quarantine = QuarantineHandler(output_dir=quarantine_dir)
    loader = PostgresLoader(conn_string=conn_string, batch_size=batch_size)

    # 1. Fallback variable initialization
    meta: dict[str, Any] = {"status": "failed_during_extraction"}

    # 2. Enter the file-safe context block
    with get_extractor_for_source(source) as extractor:
        for raw in extractor.extract():
            try:
                # Normalise directly from the raw data dict
                normalised = normalise_raw_item(raw)

                # load
                loader.add(normalised.model_dump(), source_file=str(source))

            except Exception as e:
                # anything that fails validation or normalisation is quarantined
                quarantine.add(raw_row=raw, error=str(e), source=str(source))

        # 3. Capture the real metadata if the loop completes without crashing
        meta = extractor.metadata()

    # final flush safely happens after the file has closed
    loader.flush()
    loader.close()  # Handled connection cleanup gracefully
    quarantine_path = quarantine.flush()

    print("Ingestion complete.")
    print("Source metadata:", meta)
    print("Quarantine file:", quarantine_path)


# --- CLI entrypoint --------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified ingestion pipeline")
    parser.add_argument("source", help="Path to input file (csv/json/txt/pdf)")
    parser.add_argument(
        "--conn-string",
        dest="conn_string",
        default=os.getenv("PREF_PIPELINE_PG_CONN", ""),
        help="Postgres connection string (or set PREF_PIPELINE_PG_CONN)",
    )
    parser.add_argument(
        "--quarantine-dir",
        dest="quarantine_dir",
        default="quarantine",
        help="Directory to write quarantine files",
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=500,
        help="Batch size for Postgres inserts",
    )

    args = parser.parse_args()

    if not args.conn_string:
        raise SystemExit("Postgres connection string is required.")

    ingest_source(
        source=args.source,
        conn_string=args.conn_string,
        quarantine_dir=args.quarantine_dir,
        batch_size=args.batch_size,
    )
