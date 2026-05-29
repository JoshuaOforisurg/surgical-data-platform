import os
import shutil
import argparse
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Optional
import psycopg2

def ensure_local_storage_exists(directory_path: str) -> None:
    """Creates the local raw landing zone directory if it does not exist yet."""
    os.makedirs(directory_path, exist_ok=True)

def register_file_in_ledger(
    conn_string: str,
    file_name: str,
    file_format: str,
    storage_path: str,
    file_size: int,
    status: str = "queued"
) -> None:
    """Creates a permanent operational audit lineage trail record inside PostgreSQL."""
    query = """
        INSERT INTO bronze_raw.unified_file_ingestion_ledger
            (file_name, file_format, storage_path, file_size_bytes, status)
        VALUES (%s, %s, %s, %s, %s);
    """

    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (file_name, file_format, storage_path, file_size, status))
            conn.commit()

def ingest_file_to_local_lake(
    source_file_path: str,
    conn_string: str,
    status: str = "queued"
) -> Optional[str]:
    """
    Main execution engine mimicking cloud storage workflows on local disks.
    Returns the destination file path if successful, otherwise None.
    """
    if not os.path.exists(source_file_path):
        print(f"[ERROR] Source file path does not exist: {source_file_path}")
        return None

    # 1. Define your local "Cloud Bucket" repository landing directory path
    local_lake_dir = os.path.abspath("./data/raw_landing")
    ensure_local_storage_exists(local_lake_dir)

    # 2. Extract file properties
    file_name = os.path.basename(source_file_path)
    file_extension = file_name.split('.')[-1].lower() if '.' in file_name else 'unknown'
    file_size_bytes = os.path.getsize(source_file_path)

    # Generate a unique destination storage target path string to prevent overwrites
    timestamp_prefix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_")
    destination_file_path = os.path.join(local_lake_dir, f"{timestamp_prefix}{file_name}")

    try:
        # 3. Save the physical file copy into your local file lake system
        shutil.copy2(source_file_path, destination_file_path)
        print(f"[SUCCESS] Physical file saved to file storage lake at: {destination_file_path}")

        # 4. Record the file location entry pointer directly into your Postgres ledger table
        register_file_in_ledger(
            conn_string=conn_string,
            file_name=file_name,
            file_format=file_extension,
            storage_path=destination_file_path,
            file_size=file_size_bytes,
            status=status
        )
        print(f"[SUCCESS] File ledger record logged into Postgres framework successfully.")
        return destination_file_path

    except Exception as e:
        print(f"[ERROR] Local landing routine failed: {e}")
        return None

def ingest_multiple_files(
    source_paths: List[str],
    conn_string: str,
    status: str = "queued"
) -> List[Optional[str]]:
    """
    Ingest multiple files into the local lake and register them in the ledger.
    Returns a list of destination file paths (or None for failed ingestions).
    """
    results = []
    for source_path in source_paths:
        result = ingest_file_to_local_lake(
            source_file_path=source_path,
            conn_string=conn_string,
            status=status
        )
        results.append(result)
    return results

def ingest_directory(
    source_dir: str,
    conn_string: str,
    status: str = "queued"
) -> List[Optional[str]]:
    """
    Ingest all files from a directory into the local lake and register them in the ledger.
    Returns a list of destination file paths (or None for failed ingestions).
    """
    source_paths = [str(file) for file in Path(source_dir).glob("*") if file.is_file()]
    return ingest_multiple_files(source_paths, conn_string, status)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local-to-Cloud Extensible Data Ingestion Framework")
    parser.add_argument(
        "--source",
        required=True,
        help="Path to raw file or directory to ingest"
    )
    parser.add_argument(
        "--conn-string",
        required=True,
        help="Postgres ledger connection string"
    )
    parser.add_argument(
        "--status",
        default="queued",
        help="Status to set for the ingested files in the ledger (default: 'queued')"
    )
    args = parser.parse_args()

    # Determine if the source is a file or directory
    source_path = Path(args.source)
    if source_path.is_file():
        ingest_file_to_local_lake(
            source_file_path=str(source_path),
            conn_string=args.conn_string,
            status=args.status
        )
    elif source_path.is_dir():
        ingest_directory(
            source_dir=str(source_path),
            conn_string=args.conn_string,
            status=args.status
        )
    else:
        print(f"[ERROR] Source path does not exist: {args.source}")
