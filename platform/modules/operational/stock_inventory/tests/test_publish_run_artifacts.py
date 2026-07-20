from __future__ import annotations

import json
from pathlib import Path

from config.settings import ObjectStoreSettings
from orchestration.publish_run_artifacts import RunArtifactPublisher


class FakeObjectStore:
    bucket = "stock-inventory"

    def __init__(self):
        self.uploads: list[dict] = []
        self.text_objects: dict[str, str] = {}

    def upload_file(self, local_path, key, content_type=None, metadata=None):
        uri = self.uri(key)
        self.uploads.append(
            {
                "local_path": str(local_path),
                "key": key,
                "content_type": content_type,
                "metadata": metadata,
                "uri": uri,
            }
        )
        return uri

    def put_text(self, key, text, content_type="text/plain"):
        self.text_objects[key] = text
        return self.uri(key)

    def uri(self, key):
        return f"s3://{self.bucket}/{key}"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_publish_run_artifacts_uploads_manifest_and_outputs(tmp_path):
    run_id = "run_publish"
    data_lake = tmp_path / "data_lake"
    bronze_record = data_lake / "bronze" / "records" / run_id / "item_catalogue__json.jsonl"
    silver_table = data_lake / "silver_b" / "records" / run_id / "stock_positions.jsonl"
    gold_artifact = data_lake / "gold" / "records" / run_id / "inventory_risk_summary.json"
    bronze_record.parent.mkdir(parents=True)
    bronze_record.write_text("{}\n", encoding="utf-8")
    silver_table.parent.mkdir(parents=True)
    silver_table.write_text("{}\n", encoding="utf-8")
    _write_json(gold_artifact, {"status": "ok"})

    bronze_manifest = data_lake / "bronze" / "manifests" / f"{run_id}.json"
    silver_b_manifest = data_lake / "silver_b" / "manifests" / f"{run_id}.json"
    gold_manifest = data_lake / "gold" / "manifests" / f"{run_id}.json"
    pipeline_manifest = data_lake / "pipeline_manifests" / f"{run_id}.json"
    _write_json(
        bronze_manifest,
        {"run_id": run_id, "record_outputs": [{"record_path": str(bronze_record)}]},
    )
    _write_json(
        silver_b_manifest,
        {"run_id": run_id, "table_outputs": [{"output_path": str(silver_table)}]},
    )
    _write_json(
        gold_manifest,
        {"run_id": run_id, "artifacts": [{"output_path": str(gold_artifact)}]},
    )
    _write_json(
        pipeline_manifest,
        {
            "run_id": run_id,
            "stages": [
                {"stage": "bronze", "manifest_path": str(bronze_manifest), "record_count": 1},
                {"stage": "silver_b", "manifest_path": str(silver_b_manifest), "record_count": 1},
                {"stage": "gold", "manifest_path": str(gold_manifest), "record_count": 1},
            ],
        },
    )
    fake_store = FakeObjectStore()
    settings = ObjectStoreSettings(
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="stock-inventory",
        secure=False,
        root_prefix="stock_inventory",
    )

    result = RunArtifactPublisher(fake_store, settings).publish(pipeline_manifest)

    uploaded_keys = {upload["key"] for upload in fake_store.uploads}
    assert result.status == "published"
    assert result.artifact_count == 7
    assert f"stock_inventory/runs/{run_id}/data_lake/pipeline_manifests/{run_id}.json" in uploaded_keys
    assert f"stock_inventory/runs/{run_id}/data_lake/bronze/manifests/{run_id}.json" in uploaded_keys
    assert f"stock_inventory/runs/{run_id}/data_lake/gold/records/{run_id}/inventory_risk_summary.json" in uploaded_keys
    assert f"stock_inventory/runs/{run_id}/publish_manifest.json" in fake_store.text_objects
