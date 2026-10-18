from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import mimetypes
import csv as csv_module
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.pipeline_version import (
    ANALYTICS_DATA_PRODUCT_VERSION,
    ANALYTICS_SCHEMA_VERSION,
    DATA_PRODUCT_VERSION,
    GOLD_SCHEMA_VERSION,
    PIPELINE_VERSION,
)
from config.settings import PipelineSettings
from contracts import validate_silver_to_gold_records
from gold_cleaned.clinical_analytics import ClinicalGoldAnalytics
from gold_cleaned.operational_preference_card import OperationalPreferenceGoldBuilder
from orchestration.run_identity import new_run_id
from orchestration.quality_gate import evaluate_silver_quality
from silver_transform.silver_a.file_format_reader import FileReader
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher
from storage.object_store import ObjectStoreClient, sha256_file
from streamlit_services.preference_card_repository import PreferenceCardRepository


LOGGER = logging.getLogger(__name__)


class MinIOMedallionPipeline:
    def __init__(self, settings: PipelineSettings):
        self.settings = settings
        self.object_store = ObjectStoreClient(settings.minio)
        self.catalog = BronzeCatalogRepository(settings.postgres)
        self.silver_a = SilverTransformer()
        self.silver_b = SilverBBatchEnricher(log_enabled=True)
        self.operational_gold = OperationalPreferenceGoldBuilder()
        self.analytics_gold = ClinicalGoldAnalytics()
        self.preference_card_repository = PreferenceCardRepository(settings.postgres)

    def run(
        self, source_path: Path, replay_of_run_id: str | None = None
    ) -> Dict[str, Any]:
        run_id = new_run_id()
        source_path = Path(source_path)
        LOGGER.info("Starting surgeon preference pipeline run_id=%s source=%s", run_id, source_path)

        self.catalog.initialise()
        self.catalog.start_run(
            run_id,
            str(source_path),
            pipeline_version=PIPELINE_VERSION,
            data_product_version=DATA_PRODUCT_VERSION,
            replay_of_run_id=replay_of_run_id,
        )

        landed_files: List[Dict[str, Any]] = []
        all_raw_records: list[dict[str, Any]] = []
        quarantined_files: list[Dict[str, Any]] = []
        active_stage = "landing"

        try:
            self.catalog.record_stage(run_id, active_stage, "running")
            self.object_store.wait_until_ready()
            self.catalog.bootstrap_iceberg_catalog(
                warehouse_uri=self.object_store.uri("iceberg-warehouse")
            )
            landed_files = self._land_source_files(source_path, run_id)
            self.catalog.record_stage(
                run_id, active_stage, "completed", records_received=len(landed_files), completed=True
            )

            active_stage = "bronze"
            self.catalog.record_stage(run_id, active_stage, "running")
            with TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                for landed in landed_files:
                    file_id = landed["file_id"]
                    local_copy = tmpdir_path / landed["original_filename"]
                    self.object_store.download_file(landed["object_key"], local_copy)
                    try:
                        records = self._extract_records(local_copy)
                    except (json.JSONDecodeError, UnicodeDecodeError, csv_module.Error, ValueError) as exc:
                        quarantine = self._quarantine_source_file(run_id, landed, exc)
                        quarantined_files.append(quarantine)
                        continue
                    self.catalog.write_records(file_id, run_id, records)
                    self.catalog.update_file_status(file_id, "bronze_registered")
                    self.catalog.update_run_file(run_id, file_id, "bronze_registered", len(records))
                    all_raw_records.extend(records)

            LOGGER.info("Bronze extraction complete records=%s", len(all_raw_records))
            self.catalog.record_stage(
                run_id, active_stage, "completed",
                records_received=len(all_raw_records),
                records_processed=len(all_raw_records),
                records_rejected=len(quarantined_files), completed=True,
            )

            active_stage = "silver_a"
            self.catalog.record_stage(run_id, active_stage, "running", records_received=len(all_raw_records))
            silver_a_records = self.silver_a.transform_records(
                all_raw_records,
                run_id=run_id,
            )
            self.catalog.record_stage(
                run_id, active_stage, "completed", records_received=len(all_raw_records),
                records_processed=len(silver_a_records), completed=True,
            )

            active_stage = "silver_b"
            self.catalog.record_stage(
                run_id, active_stage, "running", records_received=len(silver_a_records)
            )
            silver_b_records = self.silver_b.process(
                silver_a_records,
                run_id=run_id,
            )
            silver_stats = self.silver_b.get_stats()
            self.catalog.record_stage(
                run_id, active_stage, "completed",
                records_received=len(silver_a_records),
                records_processed=len(silver_b_records),
                records_rejected=int(silver_stats.get("quarantined", 0))
                + int(silver_stats.get("failed", 0)),
                completed=True,
            )
            silver_keys = self._publish_silver(run_id)
            quality_summary = evaluate_silver_quality(
                self.silver_b.get_stats(),
                output_record_count=len(silver_b_records),
            )
            contract_summary = validate_silver_to_gold_records(silver_b_records)

            active_stage = "gold"
            self.catalog.record_stage(run_id, active_stage, "running", records_received=len(silver_b_records))
            operational = self.operational_gold.build_and_write(silver_b_records)
            analytics_report = self.analytics_gold.full_report(silver_b_records)

            gold_keys = self._publish_gold(run_id, operational["rows"], analytics_report)
            self.catalog.record_stage(
                run_id, active_stage, "completed",
                records_received=len(silver_b_records),
                records_processed=len(operational["rows"]), completed=True,
            )

            active_stage = "operational_sync"
            self.catalog.record_stage(run_id, active_stage, "running", records_received=len(operational["rows"]))
            operational_sync_summary = self._sync_operational_current_cards(
                operational_rows=operational["rows"],
                gold_keys=gold_keys,
            )
            self.catalog.record_stage(
                run_id, active_stage, "completed",
                records_received=len(operational["rows"]),
                records_processed=int(operational_sync_summary.get("imported", 0)),
                records_rejected=int(operational_sync_summary.get("protected", 0)),
                completed=True,
            )
            self._publish_run_manifest(
                run_id=run_id,
                landed_files=landed_files,
                quarantined_files=quarantined_files,
                records_processed=len(all_raw_records),
                silver_keys=silver_keys,
                gold_keys=gold_keys,
                quality_summary=quality_summary,
                contract_summary=contract_summary,
                operational_sync_summary=operational_sync_summary,
            )

            self.catalog.complete_run(
                run_id=run_id,
                status="completed",
                files_landed=len(landed_files),
                records_processed=len(all_raw_records),
                gold_operational_key=gold_keys["operational_latest_csv"],
                gold_analytics_key=gold_keys["analytics_latest_json"],
                records_received=len(all_raw_records),
                records_rejected=int(silver_stats.get("failed", 0)) + len(quarantined_files),
                records_quarantined=int(silver_stats.get("quarantined", 0)),
                records_published=len(operational["rows"]),
            )

            LOGGER.info(
                "Pipeline completed run_id=%s files=%s records=%s gold=%s",
                run_id,
                len(landed_files),
                len(all_raw_records),
                gold_keys["operational_latest_csv"],
            )

            return {
                "run_id": run_id,
                "pipeline_version": PIPELINE_VERSION,
                "data_product_version": DATA_PRODUCT_VERSION,
                "gold_schema_version": GOLD_SCHEMA_VERSION,
                "analytics_schema_version": ANALYTICS_SCHEMA_VERSION,
                "analytics_data_product_version": ANALYTICS_DATA_PRODUCT_VERSION,
                "files_landed": len(landed_files),
                "files_quarantined": len(quarantined_files),
                "records_processed": len(all_raw_records),
                "quality_summary": quality_summary,
                "contract_summary": contract_summary,
                "operational_sync_summary": operational_sync_summary,
                "silver_keys": silver_keys,
                "gold_keys": gold_keys,
            }

        except Exception as exc:
            LOGGER.exception("Pipeline failed run_id=%s", run_id)
            try:
                self.catalog.record_stage(
                    run_id, active_stage, "failed", error_message=str(exc), completed=True
                )
                self.catalog.complete_run(
                    run_id=run_id,
                    status="failed",
                    files_landed=len(landed_files),
                    records_processed=len(all_raw_records),
                    gold_operational_key=None,
                    gold_analytics_key=None,
                    error_message=str(exc),
                    records_received=len(all_raw_records),
                )
            except Exception:
                LOGGER.exception("Could not persist failure metadata run_id=%s", run_id)
            raise

    def replay_failed_run(self, failed_run_id: str) -> Dict[str, Any]:
        source_files = self.catalog.get_run_files(failed_run_id)
        if not source_files:
            raise ValueError(f"No landed source files are available for run {failed_run_id}.")

        with TemporaryDirectory(prefix=f"replay-{failed_run_id}-") as tmpdir:
            replay_dir = Path(tmpdir)
            for index, source in enumerate(source_files):
                filename = Path(source["original_filename"]).name
                local_path = replay_dir / str(index) / filename
                self.object_store.download_file(source["object_key"], local_path)
                actual_checksum = sha256_file(local_path)
                if actual_checksum != source["checksum_sha256"]:
                    raise ValueError(
                        f"Checksum mismatch while replaying source object {source['object_key']}."
                    )
            return self.run(replay_dir, replay_of_run_id=failed_run_id)

    def _land_source_files(self, source_path: Path, run_id: str) -> List[Dict[str, Any]]:
        files = self._source_files(source_path)
        landed_files = []

        for file_path in files:
            checksum = sha256_file(file_path)
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            object_key = (
                f"{self.settings.minio.landing_prefix.strip('/')}/content/"
                f"{checksum}/{file_path.name}"
            )
            object_uri = self.object_store.upload_file(
                file_path,
                object_key,
                content_type=content_type,
                metadata={"checksum-sha256": checksum, "run-id": run_id},
            )
            metadata = {
                "run_id": run_id,
                "bucket": self.object_store.bucket,
                "object_key": object_key,
                "object_uri": object_uri,
                "original_filename": file_path.name,
                "file_extension": file_path.suffix.lower().lstrip(".") or "unknown",
                "content_type": content_type,
                "size_bytes": file_path.stat().st_size,
                "checksum_sha256": checksum,
            }
            file_id = self.catalog.register_file(metadata)
            self.catalog.register_run_file(run_id, file_id)
            self.catalog.register_object(
                {
                    **metadata,
                    "layer": "landing",
                    "artifact_type": "source_file",
                    "source_filename": file_path.name,
                }
            )
            landed = {**metadata, "file_id": file_id}
            landed_files.append(landed)
            LOGGER.info("Landed file name=%s key=%s", file_path.name, object_key)

        return landed_files

    def _source_files(self, source_path: Path) -> List[Path]:
        if source_path.is_file():
            return [source_path]
        if source_path.is_dir():
            return sorted(path for path in source_path.rglob("*") if path.is_file())
        raise FileNotFoundError(f"Source path does not exist: {source_path}")

    def _quarantine_source_file(
        self, run_id: str, landed: Dict[str, Any], error: Exception
    ) -> Dict[str, Any]:
        details = {
            "run_id": run_id,
            "source_file_id": str(landed["file_id"]),
            "source_object_key": landed["object_key"],
            "source_filename": landed["original_filename"],
            "source_checksum_sha256": landed["checksum_sha256"],
            "quarantined_at": datetime.now(UTC).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        body = json.dumps(details, indent=2)
        object_key = (
            f"{self.settings.minio.bronze_prefix}/quarantine/runs/"
            f"{run_id}/{landed['file_id']}.json"
        )
        self.object_store.put_text(object_key, body, "application/json")
        self.catalog.register_object(
            {
                "run_id": run_id,
                "bucket": self.object_store.bucket,
                "object_key": object_key,
                "object_uri": self.object_store.uri(object_key),
                "layer": "bronze",
                "artifact_type": "quarantined_source_file",
                "content_type": "application/json",
                "size_bytes": len(body.encode("utf-8")),
                "checksum_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "source_filename": landed["original_filename"],
            }
        )
        message = f"{type(error).__name__}: {error}"
        self.catalog.update_file_status(landed["file_id"], "quarantined", message)
        self.catalog.update_run_file(run_id, landed["file_id"], "quarantined")
        LOGGER.warning(
            "Quarantined malformed source file run_id=%s file_id=%s error=%s",
            run_id,
            landed["file_id"],
            message,
        )
        return {**details, "quarantine_object_key": object_key}

    def _extract_records(self, local_path: Path) -> List[Dict[str, Any]]:
        if local_path.suffix.lower() == ".json":
            return self._read_json_or_jsonl(local_path)

        payload = FileReader.read_file(local_path)
        content = payload.get("content")
        if isinstance(content, list):
            return [record for record in content if isinstance(record, dict)]
        if isinstance(content, dict):
            return [content]
        return []

    def _read_json_or_jsonl(self, local_path: Path) -> List[Dict[str, Any]]:
        text = local_path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []

    def _publish_gold(
        self,
        run_id: str,
        operational_rows: List[Dict[str, Any]],
        analytics_report: Dict[str, Any],
    ) -> Dict[str, str]:
        operational_csv = self._rows_to_csv(operational_rows)
        operational_json = json.dumps(operational_rows, indent=2)
        analytics_json = json.dumps(analytics_report, indent=2)

        gold_prefix = self.settings.minio.gold_prefix
        run_prefix = f"{gold_prefix}/operational/runs/{run_id}"
        analytics_run_prefix = f"{gold_prefix}/analytics/runs/{run_id}"

        keys = {
            "operational_run_csv": f"{run_prefix}/gold_operational_preference_cards.csv",
            "operational_run_json": f"{run_prefix}/gold_operational_preference_cards.json",
            "analytics_run_json": f"{analytics_run_prefix}/gold_analytics_report.json",
            "operational_latest_csv": f"{gold_prefix}/operational/latest/gold_operational_preference_cards.csv",
            "operational_latest_json": f"{gold_prefix}/operational/latest/gold_operational_preference_cards.json",
            "analytics_latest_json": f"{gold_prefix}/analytics/latest/gold_analytics_report.json",
        }

        self.object_store.put_text(keys["operational_run_csv"], operational_csv, "text/csv")
        self.object_store.put_text(keys["operational_run_json"], operational_json, "application/json")
        self.object_store.put_text(keys["analytics_run_json"], analytics_json, "application/json")
        self.object_store.put_text(keys["operational_latest_csv"], operational_csv, "text/csv")
        self.object_store.put_text(keys["operational_latest_json"], operational_json, "application/json")
        self.object_store.put_text(keys["analytics_latest_json"], analytics_json, "application/json")
        self._register_published_objects(
            run_id,
            {
                keys["operational_run_csv"]: ("gold", "operational_run_csv", "text/csv", operational_csv),
                keys["operational_run_json"]: (
                    "gold",
                    "operational_run_json",
                    "application/json",
                    operational_json,
                ),
                keys["analytics_run_json"]: ("gold", "analytics_run_json", "application/json", analytics_json),
                keys["operational_latest_csv"]: (
                    "gold",
                    "operational_latest_csv",
                    "text/csv",
                    operational_csv,
                ),
                keys["operational_latest_json"]: (
                    "gold",
                    "operational_latest_json",
                    "application/json",
                    operational_json,
                ),
                keys["analytics_latest_json"]: (
                    "gold",
                    "analytics_latest_json",
                    "application/json",
                    analytics_json,
                ),
            },
        )
        operational_artifacts = {
            artifact_name: object_key
            for artifact_name, object_key in keys.items()
            if artifact_name.startswith("operational_")
        }
        analytics_artifacts = {
            artifact_name: object_key
            for artifact_name, object_key in keys.items()
            if artifact_name.startswith("analytics_")
        }
        self.catalog.register_gold_artifacts(
            run_id=run_id,
            artifacts=operational_artifacts,
            record_count=len(operational_rows),
            schema_version=GOLD_SCHEMA_VERSION,
            data_product_version=DATA_PRODUCT_VERSION,
        )
        self.catalog.register_gold_artifacts(
            run_id=run_id,
            artifacts=analytics_artifacts,
            record_count=int(analytics_report.get("source_record_count") or 0),
            schema_version=ANALYTICS_SCHEMA_VERSION,
            data_product_version=ANALYTICS_DATA_PRODUCT_VERSION,
        )

        return keys

    def _sync_operational_current_cards(
        self,
        operational_rows: List[Dict[str, Any]],
        gold_keys: Dict[str, str],
    ) -> Dict[str, Any]:
        summary = self.preference_card_repository.import_gold_rows(
            rows=operational_rows,
            source_gold_key=gold_keys["operational_latest_csv"],
            imported_by="pipeline",
        )
        result = {
            "enabled": summary.enabled,
            "imported": summary.imported,
            "unchanged": getattr(summary, "unchanged", 0),
            "protected": getattr(summary, "protected", 0),
            "organisation_id": summary.organisation_id,
            "source_gold_key": summary.source_gold_key,
            "message": summary.message,
        }
        LOGGER.info(
            "Operational current-card sync enabled=%s imported=%s source=%s",
            result["enabled"],
            result["imported"],
            result["source_gold_key"],
        )
        return result

    def _publish_silver(self, run_id: str) -> Dict[str, str]:
        silver_prefix = self.settings.minio.silver_prefix
        silver_b_paths = self.silver_b.output_paths(run_id)
        artifacts = {
            "silver_a_cleaned": (
                self.silver_a.output_path(run_id),
                f"{silver_prefix}/a/runs/{run_id}/silver_a_cleaned.jsonl",
            ),
            "silver_b_enriched": (
                silver_b_paths["clean"],
                f"{silver_prefix}/b/runs/{run_id}/silver_b_enriched.jsonl",
            ),
            "silver_b_quarantine": (
                silver_b_paths["quarantine"],
                f"{silver_prefix}/b/runs/{run_id}/silver_b_quarantine.jsonl",
            ),
        }

        keys: Dict[str, str] = {}
        for artifact_type, (local_path, object_key) in artifacts.items():
            object_uri = self.object_store.upload_file(
                local_path,
                object_key,
                content_type="application/x-ndjson",
                metadata={"run-id": run_id, "artifact-type": artifact_type},
            )
            self.catalog.register_object(
                {
                    "run_id": run_id,
                    "bucket": self.object_store.bucket,
                    "object_key": object_key,
                    "object_uri": object_uri,
                    "layer": "silver",
                    "artifact_type": artifact_type,
                    "content_type": "application/x-ndjson",
                    "size_bytes": local_path.stat().st_size,
                    "checksum_sha256": sha256_file(local_path),
                    "source_filename": local_path.name,
                }
            )
            keys[artifact_type] = object_key

        return keys

    def _publish_run_manifest(
        self,
        run_id: str,
        landed_files: List[Dict[str, Any]],
        records_processed: int,
        silver_keys: Dict[str, str],
        gold_keys: Dict[str, str],
        quality_summary: Dict[str, Any],
        contract_summary: Dict[str, Any],
        operational_sync_summary: Dict[str, Any],
        quarantined_files: List[Dict[str, Any]] | None = None,
    ) -> None:
        manifest = {
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "pipeline_version": PIPELINE_VERSION,
            "gold_schema_version": GOLD_SCHEMA_VERSION,
            "data_product_version": DATA_PRODUCT_VERSION,
            "analytics_schema_version": ANALYTICS_SCHEMA_VERSION,
            "analytics_data_product_version": ANALYTICS_DATA_PRODUCT_VERSION,
            "landed_files": [
                {
                    "file_id": str(item["file_id"]),
                    "object_key": item["object_key"],
                    "checksum_sha256": item["checksum_sha256"],
                    "size_bytes": item["size_bytes"],
                }
                for item in landed_files
            ],
            "quarantined_files": quarantined_files or [],
            "records_processed": records_processed,
            "quality_summary": quality_summary,
            "contract_summary": contract_summary,
            "operational_sync_summary": operational_sync_summary,
            "silver_keys": silver_keys,
            "gold_keys": gold_keys,
        }
        key = f"{self.settings.minio.bronze_prefix}/manifests/{run_id}.json"
        manifest_json = json.dumps(manifest, indent=2)
        self.object_store.put_text(key, manifest_json, "application/json")
        self._register_published_objects(
            run_id,
            {key: ("bronze", "run_manifest", "application/json", manifest_json)},
        )

    def _register_published_objects(
        self,
        run_id: str,
        objects: Dict[str, tuple[str, str, str, str]],
    ) -> None:
        for object_key, (layer, artifact_type, content_type, text) in objects.items():
            data = text.encode("utf-8")
            self.catalog.register_object(
                {
                    "run_id": run_id,
                    "bucket": self.object_store.bucket,
                    "object_key": object_key,
                    "object_uri": self.object_store.uri(object_key),
                    "layer": layer,
                    "artifact_type": artifact_type,
                    "content_type": content_type,
                    "size_bytes": len(data),
                    "checksum_sha256": hashlib.sha256(data).hexdigest(),
                    "source_filename": None,
                }
            )

    def _rows_to_csv(self, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()
