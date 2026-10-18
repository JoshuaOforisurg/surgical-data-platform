from types import SimpleNamespace

from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher


class RecordingObjectStore:
    bucket = "test-bucket"

    def __init__(self):
        self.uploads = []
        self.text_objects = {}

    def upload_file(self, local_path, key, content_type=None, metadata=None):
        self.uploads.append(
            {
                "local_path": local_path,
                "key": key,
                "content_type": content_type,
                "metadata": metadata,
            }
        )
        return f"s3://{self.bucket}/{key}"

    def put_text(self, key, text, content_type=None):
        self.text_objects[key] = {
            "text": text,
            "content_type": content_type,
        }

    def uri(self, key):
        return f"s3://{self.bucket}/{key}"


class RecordingCatalog:
    def __init__(self):
        self.objects = []

    def register_object(self, metadata):
        self.objects.append(metadata)


class RecordingPreferenceCardRepository:
    def __init__(self):
        self.calls = []

    def import_gold_rows(self, rows, source_gold_key, imported_by="pipeline"):
        rows = list(rows)
        self.calls.append(
            {
                "rows": rows,
                "source_gold_key": source_gold_key,
                "imported_by": imported_by,
            }
        )
        return SimpleNamespace(
            enabled=True,
            imported=len(rows),
            organisation_id="default",
            source_gold_key=source_gold_key,
            message=f"Imported {len(rows)} current preference cards.",
        )


def test_publish_silver_uploads_and_catalogues_run_artifacts(tmp_path):
    run_id = "run_20260817_140509_123456_a1b2c3d4"
    silver_a = SilverTransformer(silver_a_dir=tmp_path / "silver_a")
    silver_b = SilverBBatchEnricher(
        log_enabled=False,
        silver_a_dir=tmp_path / "silver_a",
        silver_b_dir=tmp_path / "silver_b",
    )
    silver_a_path = silver_a.output_path(run_id)
    silver_b_paths = silver_b.output_paths(run_id)

    for path, content in (
        (silver_a_path, '{"stage": "silver_a"}\n'),
        (silver_b_paths["clean"], '{"stage": "silver_b"}\n'),
        (silver_b_paths["quarantine"], ""),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    pipeline = object.__new__(MinIOMedallionPipeline)
    pipeline.settings = SimpleNamespace(minio=SimpleNamespace(silver_prefix="silver"))
    pipeline.silver_a = silver_a
    pipeline.silver_b = silver_b
    pipeline.object_store = RecordingObjectStore()
    pipeline.catalog = RecordingCatalog()

    keys = pipeline._publish_silver(run_id)

    assert keys == {
        "silver_a_cleaned": f"silver/a/runs/{run_id}/silver_a_cleaned.jsonl",
        "silver_b_enriched": f"silver/b/runs/{run_id}/silver_b_enriched.jsonl",
        "silver_b_quarantine": f"silver/b/runs/{run_id}/silver_b_quarantine.jsonl",
    }
    assert [upload["key"] for upload in pipeline.object_store.uploads] == list(keys.values())
    assert {item["artifact_type"] for item in pipeline.catalog.objects} == set(keys)
    assert all(item["run_id"] == run_id for item in pipeline.catalog.objects)
    assert all(item["checksum_sha256"] for item in pipeline.catalog.objects)


def test_operational_current_card_sync_imports_published_gold_rows():
    pipeline = object.__new__(MinIOMedallionPipeline)
    pipeline.preference_card_repository = RecordingPreferenceCardRepository()

    summary = pipeline._sync_operational_current_cards(
        operational_rows=[
            {
                "surgeon_name": "Ms Amina Clarke",
                "procedure": "Total Knee Replacement",
            }
        ],
        gold_keys={
            "operational_latest_csv": "gold/operational/latest/gold_operational_preference_cards.csv"
        },
    )

    assert summary == {
        "enabled": True,
        "imported": 1,
        "unchanged": 0,
        "protected": 0,
        "organisation_id": "default",
        "source_gold_key": "gold/operational/latest/gold_operational_preference_cards.csv",
        "message": "Imported 1 current preference cards.",
    }
    assert pipeline.preference_card_repository.calls == [
        {
            "rows": [
                {
                    "surgeon_name": "Ms Amina Clarke",
                    "procedure": "Total Knee Replacement",
                }
            ],
            "source_gold_key": "gold/operational/latest/gold_operational_preference_cards.csv",
            "imported_by": "pipeline",
        }
    ]


def test_run_manifest_records_operational_sync_summary():
    run_id = "run_20261007_100000_000000_abcdef12"
    pipeline = object.__new__(MinIOMedallionPipeline)
    pipeline.settings = SimpleNamespace(minio=SimpleNamespace(bronze_prefix="bronze"))
    pipeline.object_store = RecordingObjectStore()
    pipeline.catalog = RecordingCatalog()

    pipeline._publish_run_manifest(
        run_id=run_id,
        landed_files=[],
        records_processed=1,
        silver_keys={"silver_a_cleaned": "silver/a.jsonl"},
        gold_keys={"operational_latest_csv": "gold/latest.csv"},
        quality_summary={"passed": True},
        contract_summary={"passed": True},
        operational_sync_summary={
            "enabled": True,
            "imported": 1,
            "organisation_id": "default",
            "source_gold_key": "gold/latest.csv",
            "message": "Imported 1 current preference cards.",
        },
    )

    manifest = pipeline.object_store.text_objects[f"bronze/manifests/{run_id}.json"]
    assert manifest["content_type"] == "application/json"
    assert '"operational_sync_summary"' in manifest["text"]
    assert '"imported": 1' in manifest["text"]
    assert pipeline.catalog.objects[0]["artifact_type"] == "run_manifest"
