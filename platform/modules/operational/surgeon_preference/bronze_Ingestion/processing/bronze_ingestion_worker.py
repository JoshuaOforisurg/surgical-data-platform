import csv
import json
import argparse
from datetime import datetime, UTC
import psycopg2
from psycopg2.extras import execute_values


def get_queued_files(conn_string: str) -> list:
    """Queries the ledger for any raw landing files awaiting processing."""
    query = """
        SELECT file_id, file_name, file_format, storage_path 
        FROM bronze_raw.unified_file_ingestion_ledger
        WHERE status = 'queued'
        ORDER BY created_at ASC;
    """
    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def update_ledger_status(conn_string: str, file_id: str, status: str, error_message: str = None) -> None:
    """Updates the file lifecycle status tracking inside the database ledger."""
    query = """
        UPDATE bronze_raw.unified_file_ingestion_ledger
        SET status = %s, extraction_error = %s, updated_at = CURRENT_TIMESTAMP
        WHERE file_id = %s;
    """
    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (status, error_message, file_id))
            conn.commit()


def process_csv_file(storage_path: str, file_name: str, conn_string: str) -> None:
    """Reads rows from the raw file storage path and dumps them as JSONB records."""
    records_to_insert = []

    with open(storage_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # FIX: Prevent crash if an empty row or None keys creep into dirty CSV entries
            if not row:
                continue
            clean_row = {
                str(k).strip(): (str(v).strip() if v is not None else None)
                for k, v in row.items()
                if k is not None
            }
            raw_payload = json.dumps(clean_row)
            records_to_insert.append((raw_payload, file_name))

    if not records_to_insert:
        print(f" -> [INFO] CSV file {file_name} was empty. Skipping database entry.")
        return

    insert_query = """
        INSERT INTO bronze_raw.surgeon_preference_items (raw_payload, source_file)
        VALUES %s;
    """
    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            execute_values(cur, insert_query, records_to_insert)
            conn.commit()
            print(f" -> [SUCCESS] Appended {len(records_to_insert)} raw rows to table.")


def run_processing_pipeline(conn_string: str) -> None:
    """Orchestrates loop cycles across all unprocessed files inside the ledger."""
    queued_files = get_queued_files(conn_string)

    if not queued_files:
        print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] No pending queued files found in ledger.")
        return

    print(f"Found {len(queued_files)} file(s) awaiting transformation processing...\n")

    for file_id, file_name, file_format, storage_path in queued_files:
        print(f"Processing File [{file_id}]: {file_name} ({file_format.upper()})")

        # 1. Flip file status to processing to secure a thread lock
        update_ledger_status(conn_string, file_id, 'processing')

        try:
            # 2. Extract and parse data fields based on format criteria
            if file_format == 'csv':
                process_csv_file(storage_path, file_name, conn_string)
                # 3. Mark file fully handled
                update_ledger_status(conn_string, file_id, 'completed')
                print(f"Finished processing package tracking item successfully.\n")
            else:
                print(f" -> [WARNING] Parsing parser module for type '{file_format}' not integrated yet.")
                update_ledger_status(conn_string, file_id, 'failed', "Parser not integrated yet")

        except Exception as e:
            # FIX: Safe row recovery log. The current file is marked as failed,
            # but the loop continues immediately to process the next file in queue.
            print(f" -> [CRITICAL ERROR] Failed parsing file contents: {e}\n")
            update_ledger_status(conn_string, file_id, 'failed', str(e))
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Silver Parsing Execution Engine Worker Daemon CLI")
    parser.add_argument("--conn-string", required=True, help="Database target connection registry string")
    args = parser.parse_args()

    run_processing_pipeline(conn_string=args.conn_string)
