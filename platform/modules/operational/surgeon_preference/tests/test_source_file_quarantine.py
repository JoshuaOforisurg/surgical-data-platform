import json
from types import SimpleNamespace

from orchestration.minio_medallion_pipeline import MinIOMedallionPipeline


class StubObjectStore:
    bucket = "surgeon-preference"

    def __init__(self):
        self.objects = {}

    def put_text(self, key, body, content_type):
        self.objects[key] = (body, content_type)

    def uri(self, key):
        return f"s3://{self.bucket}/{key}"


class StubCatalog:
    def __init__(self):
        self.objects = []
        self.file_status = None
        self.run_file_status = None

    def register_object(self, metadata):
        self.objects.append(metadata)

    def update_file_status(self, file_id, status, error_message=None):
        self.file_status = (file_id, status, error_message)

    def update_run_file(self, run_id, file_id, status, record_count=0):
        self.run_file_status = (run_id, file_id, status, record_count)


def test_malformed_source_file_is_quarantined_with_lineage_and_error():
    pipeline = MinIOMedallionPipeline.__new__(MinIOMedallionPipeline)
    pipeline.settings = SimpleNamespace(
        minio=SimpleNamespace(bronze_prefix="bronze")
    )
    pipeline.object_store = StubObjectStore()
    pipeline.catalog = StubCatalog()
    landed = {
        "file_id": "file-123",
        "object_key": "landing/content/checksum/bad.json",
        "original_filename": "bad.json",
        "checksum_sha256": "checksum",
    }

    result = pipeline._quarantine_source_file(
        "run-456", landed, json.JSONDecodeError("invalid JSON", "{", 1)
    )

    key = "bronze/quarantine/runs/run-456/file-123.json"
    body, content_type = pipeline.object_store.objects[key]
    manifest = json.loads(body)
    assert content_type == "application/json"
    assert manifest["source_object_key"] == landed["object_key"]
    assert manifest["source_checksum_sha256"] == "checksum"
    assert manifest["error_type"] == "JSONDecodeError"
    assert result["quarantine_object_key"] == key
    assert pipeline.catalog.objects[0]["artifact_type"] == "quarantined_source_file"
    assert pipeline.catalog.file_status[1] == "quarantined"
    assert pipeline.catalog.run_file_status[:3] == (
        "run-456", "file-123", "quarantined"
    )
