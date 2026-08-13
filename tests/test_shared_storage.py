from __future__ import annotations

from dataclasses import dataclass

from shared.storage import object_store
from shared.storage.object_store import (
    ObjectStoreClient,
    content_type_for,
    normalise_metadata,
    sha256_file,
)


@dataclass(frozen=True)
class Settings:
    endpoint: str = "http://localhost:9000"
    access_key: str = "local-user"
    secret_key: str = "local-password"
    bucket: str = "test-bucket"
    secure: bool = False


def test_helpers_are_provider_neutral(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text('{"ok": true}', encoding="utf-8")

    assert normalise_metadata({"run-id": 42}) == {"run_id": "42"}
    assert content_type_for(path) == "application/json"
    assert len(sha256_file(path)) == 64


def test_factory_selects_azure_when_configured(monkeypatch):
    sentinel = object()
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(object_store, "AzureBlobObjectStoreClient", lambda settings: sentinel)

    assert ObjectStoreClient(Settings()) is sentinel


def test_factory_defaults_to_s3(monkeypatch):
    sentinel = object()
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(object_store, "S3ObjectStoreClient", lambda settings: sentinel)

    assert ObjectStoreClient(Settings()) is sentinel
