"""Read-only checks of a local pipeline run and its operational publication."""

from __future__ import annotations

import argparse
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import load_settings
from storage.object_store import ObjectStoreClient
from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    card_key_for_row,
)


def require_local_services(settings) -> None:
    if (
        not settings.postgres
        or settings.postgres.host not in {"localhost", "127.0.0.1", "::1"}
        or urlparse(settings.minio.endpoint).hostname not in {"localhost", "127.0.0.1", "::1"}
        or os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    ):
        raise ValueError("Verification requires local Postgres and MinIO; Azure must be unset.")


def verify() -> dict:
    settings = load_settings()
    require_local_services(settings)

    with psycopg2.connect(settings.postgres.psycopg2_dsn) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET statement_timeout = '10s'")
            cur.execute("SELECT * FROM pipeline_audit.pipeline_runs ORDER BY started_at DESC LIMIT 1")
            run = cur.fetchone()
            if not run:
                raise ValueError("No pipeline run found. Run main_orchestrator.py first.")
            cur.execute(
                "SELECT count(*) AS files, sum(record_count) AS records "
                "FROM bronze_raw.ingested_files WHERE run_id = %s",
                (run["run_id"],),
            )
            bronze = dict(cur.fetchone())
            cur.execute(
                "SELECT count(*) AS count FROM metadata_catalog.gold_artifacts WHERE run_id = %s",
                (run["run_id"],),
            )
            artifacts = cur.fetchone()["count"]
            cur.execute(
                """
                SELECT count(*) AS count FROM app_workflow.preference_cards c
                LEFT JOIN app_workflow.preference_card_versions v ON c.current_version_id = v.version_id
                WHERE c.organisation_id = 'default' AND c.status = 'active'
                  AND (v.version_id IS NULL OR NOT v.is_current OR v.card_id <> c.card_id
                    OR v.organisation_id <> c.organisation_id
                    OR v.version_number <> c.current_version_number
                    OR (SELECT count(*) FROM app_workflow.preference_card_versions h
                        WHERE h.card_id = c.card_id AND h.is_current) <> 1)
                """
            )
            invalid_pointers = cur.fetchone()["count"]
            cur.execute(
                "SELECT change_type, count(*) AS count FROM app_workflow.preference_card_versions "
                "WHERE organisation_id = 'default' GROUP BY change_type ORDER BY change_type"
            )
            versions = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT status FROM iceberg_catalog.catalog_bootstrap")
            iceberg = [row["status"] for row in cur.fetchall()]

    store = ObjectStoreClient(settings.minio)
    manifest_key = f"{settings.minio.bronze_prefix}/manifests/{run['run_id']}.json"
    manifest = json.loads(store.get_text(manifest_key))
    gold_key = manifest["gold_keys"]["operational_latest_csv"]
    gold = pd.read_csv(io.StringIO(store.get_text(gold_key)), keep_default_na=False)
    cards = PreferenceCardRepository(settings.postgres).list_current_cards(limit=1_000_000)
    db_by_key = {row["card_key"]: row for row in cards}
    gold_rows = gold.to_dict("records")
    gold_by_key = {card_key_for_row(row): row for row in gold_rows}
    json_rows = json.loads(store.get_text(manifest["gold_keys"]["operational_latest_json"]))
    json_by_key = {card_key_for_row(row): row for row in json_rows}
    fields = ("instrument_set", "equipment", "consumables", "disposables", "special_instructions")
    mismatches = []
    for key, row in gold_by_key.items():
        current = db_by_key.get(key)
        if not current or int(row["preference_card_version"]) != current["current_version_number"]:
            mismatches.append(key)
        elif any(str(row.get(field, "")) != str(current["card_payload"].get(field, "")) for field in fields):
            mismatches.append(key)
    landed_keys = set(store.list_objects(f"{settings.minio.landing_prefix}/{run['run_id']}/"))
    referenced_keys = set(manifest["silver_keys"].values()) | set(manifest["gold_keys"].values())
    missing_artifacts = []
    for key in sorted(referenced_keys):
        if not store.get_text(key).strip() and "quarantine" not in key:
            missing_artifacts.append(key)
    silver_counts = {
        name: sum(bool(line.strip()) for line in store.get_text(key).splitlines())
        for name, key in manifest["silver_keys"].items()
    }

    checks = {
        "latest_run_completed": run["status"] == "completed",
        "bronze_counts_match": bronze["files"] == run["files_landed"] > 0
        and bronze["records"] == run["records_processed"] > 0,
        "landing_files_present": len(landed_keys) == run["files_landed"]
        and all(item["object_key"] in landed_keys for item in manifest["landed_files"]),
        "quality_gate_passed": manifest["quality_summary"].get("passed") is True,
        "contract_passed": manifest["contract_summary"].get("passed") is True,
        "operational_sync_enabled": manifest["operational_sync_summary"].get("enabled") is True,
        "gold_catalogued": artifacts > 0,
        "referenced_artifacts_readable": not missing_artifacts,
        "one_gold_row_per_card": len(gold_rows) == len(gold_by_key) > 0,
        "database_keys_match_gold": set(db_by_key) == set(gold_by_key),
        "versions_and_sections_match": not mismatches,
        "gold_json_matches_csv": len(json_rows) == len(gold_rows)
        and set(json_by_key) == set(gold_by_key)
        and all(
            int(json_by_key[key]["preference_card_version"]) == int(row["preference_card_version"])
            and all(str(json_by_key[key].get(field) or "") == str(row.get(field) or "") for field in fields)
            for key, row in gold_by_key.items()
        ),
        "current_version_pointers_valid": invalid_pointers == 0,
        "frontline_sections_populated": all(
            str(row.get(field, "")).strip() not in {"", "N/A"} for row in gold_rows for field in fields
        ),
    }
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": all(checks.values()),
        "run_id": run["run_id"],
        "database": settings.postgres.database,
        "database_port": settings.postgres.port,
        "storage_endpoint": settings.minio.endpoint,
        "bucket": settings.minio.bucket,
        "files_landed": run["files_landed"],
        "records_processed": run["records_processed"],
        "gold_current_cards": len(gold_rows),
        "postgres_current_cards": len(cards),
        "gold_artifacts": artifacts,
        "silver_record_counts": silver_counts,
        "version_counts": versions,
        "iceberg_bootstrap_status": iceberg,
        "checks": checks,
        "mismatched_cards": mismatches,
        "empty_artifacts": missing_artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence file (no credentials).")
    args = parser.parse_args()
    report = verify()
    content = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
