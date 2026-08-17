from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import mimetypes
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
from gold_cleaned.clinical_analytics import ClinicalGoldAnalytics
from gold_cleaned.operational_preference_card import OperationalPreferenceGoldBuilder
from orchestration.run_identity import new_run_id
from silver_transform.silver_a.file_format_reader import FileReader
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher
from storage.object_store import ObjectStoreClient, sha256_file


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

    def run(self, source_path: Path) -> Dict[str, Any]:
        run_id = new_run_id()
        source_path = Path(source_path)
        LOGGER.info("Starting surgeon preference pipeline run_id=%s source=%s", run_id, source_path)

        self.object_store.wait_until_ready()
        self.catalog.initialise()
        self.catalog.bootstrap_iceberg_catalog(
            warehouse_uri=self.object_store.uri("iceberg-warehouse")
        )
        self.catalog.start_run(
            run_id,
            str(source_path),
            pipeline_version=PIPELINE_VERSION,
            data_product_version=DATA_PRODUCT_VERSION,
        )

        landed_files = self._land_source_files(source_path, run_id)
        all_raw_records: list[dict[str, Any]] = []

        try:
            with TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                for landed in landed_files:
                    file_id = landed["file_id"]
                    local_copy = tmpdir_path / landed["original_filename"]
                    self.object_store.download_file(landed["object_key"], local_copy)
                    records = self._extract_records(local_copy)
                    self.catalog.write_records(file_id, run_id, records)
                    self.catalog.update_file_status(file_id, "bronze_registered")
                    all_raw_records.extend(records)

            LOGGER.info("Bronze extraction complete records=%s", len(all_raw_records))

            silver_a_records = self.silver_a.transform_records(
                all_raw_records,
                run_id=run_id,
            )
            silver_b_records = self.silver_b.process(
                silver_a_records,
                run_id=run_id,
            )
            silver_keys = self._publish_silver(run_id)

            operational = self.operational_gold.build_and_write(silver_b_records)
            analytics_report = self.analytics_gold.full_report(silver_b_records)

            gold_keys = self._publish_gold(run_id, operational["rows"], analytics_report)
            self._publish_run_manifest(
                run_id=run_id,
                landed_files=landed_files,
                records_processed=len(all_raw_records),
                silver_keys=silver_keys,
                gold_keys=gold_keys,
            )

            self.catalog.complete_run(
                run_id=run_id,
                status="completed",
                files_landed=len(landed_files),
                records_processed=len(all_raw_records),
                gold_operational_key=gold_keys["operational_latest_csv"],
                gold_analytics_key=gold_keys["analytics_latest_json"],
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
                "records_processed": len(all_raw_records),
                "silver_keys": silver_keys,
                "gold_keys": gold_keys,
            }

        except Exception as exc:
            LOGGER.exception("Pipeline failed run_id=%s", run_id)
            self.catalog.complete_run(
                run_id=run_id,
                status="failed",
                files_landed=len(landed_files),
                records_processed=len(all_raw_records),
                gold_operational_key=None,
                gold_analytics_key=None,
                error_message=str(exc),
            )
            raise

    def _land_source_files(self, source_path: Path, run_id: str) -> List[Dict[str, Any]]:
        files = self._source_files(source_path)
        landed_files = []

        for file_path in files:
            checksum = sha256_file(file_path)
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            object_key = (
                f"{self.settings.minio.landing_prefix}/{run_id}/"
                f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}_{file_path.name}"
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
            "records_processed": records_processed,
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
