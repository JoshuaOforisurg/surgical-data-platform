import os
import shutil
import argparse
from datetime import datetime, UTC
import psycopg2


def ensure_local_storage_exists(directory_path: str) -> None:
    """Creates the local raw landing zone directory if it does not exist yet."""
    os.makedirs(directory_path, exist_ok=True)


def register_file_in_ledger(conn_string: str, file_name: str, file_format: str, storage_path: str,
                            file_size: int) -> None:
    """Creates a permanent operational audit lineage trail record inside PostgreSQL."""
    query = """
        INSERT INTO bronze_raw.unified_file_ingestion_ledger 
            (file_name, file_format, storage_path, file_size_bytes, status) 
        VALUES (%s, %s, %s, %s, 'queued');
    """

    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (file_name, file_format, storage_path, file_size))
            conn.commit()


def ingest_file_to_local_lake(source_file_path: str, conn_string: str) -> None:
    """Main execution engine mimicking cloud storage workflows on local disks."""
    if not os.path.exists(source_file_path):
        print(f"[ERROR] Source file path does not exist: {source_file_path}")
        return

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
            file_size=file_size_bytes
        )
        print(f"[SUCCESS] File ledger record logged into Postgres framework successfully.")

    except Exception as e:
        print(f"[ERROR] Local landing routine failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local-to-Cloud Extensible Data Ingestion Framework")
    parser.add_argument("source", help="Path to raw file to ingest")
    parser.add_argument("--conn-string", required=True, help="Postgres ledger connection string")
    args = parser.parse_args()

    ingest_file_to_local_lake(source_file_path=args.source, conn_string=args.conn_string)
