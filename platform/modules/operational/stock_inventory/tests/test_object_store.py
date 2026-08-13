from __future__ import annotations

from config.settings import load_settings
from config.settings import ObjectStoreSettings
from storage.object_store import ObjectStoreClient, content_type_for, normalise_metadata, sha256_file
from shared.storage import object_store


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


def test_object_store_factory_selects_azure_when_connection_string_is_present(monkeypatch):
    settings = ObjectStoreSettings(
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="stock-inventory",
        secure=False,
        root_prefix="stock_inventory",
    )
    sentinel = object()
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(object_store, "AzureBlobObjectStoreClient", lambda selected: sentinel)

    assert ObjectStoreClient(settings) is sentinel


def test_object_store_factory_defaults_to_s3(monkeypatch):
    settings = ObjectStoreSettings(
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="stock-inventory",
        secure=False,
        root_prefix="stock_inventory",
    )
    sentinel = object()
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(object_store, "S3ObjectStoreClient", lambda selected: sentinel)

    assert ObjectStoreClient(settings) is sentinel
