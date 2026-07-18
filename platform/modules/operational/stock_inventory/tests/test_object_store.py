from __future__ import annotations

from config.settings import load_settings
from storage.object_store import content_type_for, normalise_metadata, sha256_file


def test_load_settings_uses_stock_inventory_defaults(monkeypatch):
    for name in (
        "MINIO_ENDPOINT",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
        "MINIO_BUCKET",
        "MINIO_ROOT_PREFIX",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.object_store.endpoint == "http://localhost:9000"
    assert settings.object_store.bucket == "stock-inventory"
    assert settings.object_store.root_prefix == "stock_inventory"


def test_object_store_helpers_normalise_metadata_and_hash_files(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text('{"ok": true}', encoding="utf-8")

    assert normalise_metadata({"run-id": "run_1", "checksum.sha256": "abc"}) == {
        "run_id": "run_1",
        "checksum_sha256": "abc",
    }
    assert content_type_for(path) == "application/json"
    assert sha256_file(path)
