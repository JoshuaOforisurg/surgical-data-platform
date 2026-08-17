from types import SimpleNamespace

from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher


class RecordingObjectStore:
    bucket = "test-bucket"

    def __init__(self):
        self.uploads = []

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


class RecordingCatalog:
    def __init__(self):
        self.objects = []

    def register_object(self, metadata):
        self.objects.append(metadata)


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
