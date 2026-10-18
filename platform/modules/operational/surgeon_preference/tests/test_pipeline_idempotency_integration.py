"""Disposable local Postgres/MinIO test for repeated source ingestion."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import psycopg2
import pytest
from psycopg2 import sql

from config.settings import load_settings
from generate_synthetic_data.main_synthetic_generator import generate_single_card
from gold_cleaned.operational_preference_card import OperationalPreferenceGoldBuilder
from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher
from storage.object_store import ObjectStoreClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LOCAL_PIPELINE_INTEGRATION") != "1",
    reason="Set RUN_LOCAL_PIPELINE_INTEGRATION=1 to use disposable local services.",
)


def _drop_bucket(store: ObjectStoreClient, bucket: str) -> None:
    pages = store.client.get_paginator("list_objects_v2").paginate(Bucket=bucket)
    for page in pages:
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            store.client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
    store.client.delete_bucket(Bucket=bucket)


def test_failure_is_audited_replayed_and_source_remains_idempotent():
    base = load_settings()
    endpoint_host = urlparse(base.minio.endpoint).hostname
    if (
        not base.postgres
        or base.postgres.host not in {"localhost", "127.0.0.1", "::1"}
        or endpoint_host not in {"localhost", "127.0.0.1", "::1"}
        or os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    ):
        pytest.fail("Integration test requires local Postgres/MinIO and no Azure storage setting.")

    suffix = uuid.uuid4().hex[:12]
    database_name = f"sp_retry_test_{suffix}"
    bucket_name = f"sp-retry-test-{suffix}"
    admin_settings = replace(base.postgres, database="postgres")
    minio_settings = replace(base.minio, bucket=bucket_name)
    store = ObjectStoreClient(minio_settings)
    database_created = False
    bucket_created = False

    try:
        admin_conn = psycopg2.connect(admin_settings.psycopg2_dsn)
        admin_conn.autocommit = True
        with admin_conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )
        admin_conn.close()
        database_created = True

        store.wait_until_ready()
        bucket_created = True
        test_settings = replace(
            base,
            minio=minio_settings,
            postgres=replace(base.postgres, database=database_name),
        )

        with TemporaryDirectory(prefix="sp-idempotency-") as temp:
            temp_path = Path(temp)
            source_dir = temp_path / "source"
            source_dir.mkdir()
            source_file = source_dir / "preference_card.json"
            generate_single_card(
                output_dir=str(source_dir),
                messy=False,
                export=True,
                stem=source_file.stem,
                formats=("json",),
            )

            pipeline = MinIOMedallionPipeline(test_settings)
            pipeline.silver_a = SilverTransformer(temp_path / "silver_a")
            pipeline.silver_b = SilverBBatchEnricher(
                log_enabled=False,
                silver_a_dir=temp_path / "silver_a",
                silver_b_dir=temp_path / "silver_b",
            )
            pipeline.operational_gold = OperationalPreferenceGoldBuilder(temp_path / "gold")

            original_process = pipeline.silver_b.process

            def fail_silver_b(*_args, **_kwargs):
                raise RuntimeError("injected Silver-B failure")

            pipeline.silver_b.process = fail_silver_b
            with pytest.raises(RuntimeError, match="injected Silver-B failure"):
                pipeline.run(source_dir)
            pipeline.silver_b.process = original_process

            with psycopg2.connect(test_settings.postgres.psycopg2_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT run_id FROM pipeline_audit.pipeline_runs "
                        "WHERE status = 'failed'"
                    )
                    failed_run_id = cur.fetchone()[0]
            assert store.list_objects("gold/operational/latest/") == []

            replay = pipeline.replay_failed_run(failed_run_id)
            repeated = pipeline.run(source_dir)

            with psycopg2.connect(test_settings.postgres.psycopg2_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*), sum(record_count) FROM bronze_raw.ingested_files")
                    file_count, bronze_record_count = cur.fetchone()
                    cur.execute("SELECT count(*) FROM bronze_raw.ingested_records")
                    stored_record_count = cur.fetchone()[0]
                    cur.execute(
                        "SELECT count(*), count(DISTINCT file_id) "
                        "FROM pipeline_audit.pipeline_run_files"
                    )
                    run_file_count, linked_file_count = cur.fetchone()
                    cur.execute(
                        "SELECT status, replay_of_run_id, error_message "
                        "FROM pipeline_audit.pipeline_runs"
                    )
                    run_rows = cur.fetchall()
                    cur.execute(
                        "SELECT count(*) FROM pipeline_audit.pipeline_run_stages "
                        "WHERE status = 'completed'"
                    )
                    completed_stages = cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM app_workflow.preference_cards")
                    card_count = cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM app_workflow.preference_card_versions")
                    version_count = cur.fetchone()[0]

            landing_keys = store.list_objects("landing/content/")
            assert replay["run_id"] != failed_run_id
            assert replay["records_processed"] == repeated["records_processed"]
            assert file_count == 1
            assert bronze_record_count == stored_record_count == replay["records_processed"]
            assert run_file_count == 3 and linked_file_count == 1
            assert sum(row[0] == "completed" for row in run_rows) == 2
            assert sum(row[0] == "failed" for row in run_rows) == 1
            assert any(row[0] == "completed" and row[1] == failed_run_id for row in run_rows)
            assert any(
                row[0] == "failed" and "injected Silver-B failure" in row[2]
                for row in run_rows
            )
            assert completed_stages == 15
            assert len(landing_keys) == 1
            assert card_count == 1
            assert version_count == 1
            assert repeated["operational_sync_summary"]["unchanged"] == 1
            assert store.list_objects("gold/operational/latest/")

            mixed_source = temp_path / "mixed-source"
            mixed_source.mkdir()
            generate_single_card(
                output_dir=str(mixed_source),
                messy=False,
                export=True,
                stem="valid_card",
                formats=("json",),
            )
            (mixed_source / "malformed.json").write_text("{invalid json", encoding="utf-8")

            mixed_result = pipeline.run(mixed_source)
            quarantine_keys = store.list_objects(
                f"bronze/quarantine/runs/{mixed_result['run_id']}/"
            )
            assert mixed_result["files_landed"] == 2
            assert mixed_result["files_quarantined"] == 1
            assert mixed_result["records_processed"] == 1
            assert len(quarantine_keys) == 1

            with psycopg2.connect(test_settings.postgres.psycopg2_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM pipeline_audit.pipeline_run_files "
                        "WHERE run_id = %s ORDER BY status",
                        (mixed_result["run_id"],),
                    )
                    assert [row[0] for row in cur.fetchall()] == [
                        "bronze_registered", "quarantined"
                    ]
    finally:
        if bucket_created:
            _drop_bucket(store, bucket_name)
        if database_created:
            admin_conn = psycopg2.connect(admin_settings.psycopg2_dsn)
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )
            admin_conn.close()
