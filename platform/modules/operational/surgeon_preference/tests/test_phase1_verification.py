from types import SimpleNamespace

import pytest

from scripts.verify_phase1 import require_local_services


def settings(host="127.0.0.1", endpoint="http://localhost:9000"):
    return SimpleNamespace(postgres=SimpleNamespace(host=host), minio=SimpleNamespace(endpoint=endpoint))


def test_verification_allows_only_local_services(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    require_local_services(settings())


@pytest.mark.parametrize("config", [
    settings(host="production.example.invalid"),
    settings(endpoint="https://production.example.invalid"),
    SimpleNamespace(postgres=None, minio=SimpleNamespace(endpoint="http://localhost:9000")),
])
def test_verification_rejects_nonlocal_or_missing_database(monkeypatch, config):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    with pytest.raises(ValueError, match="local Postgres and MinIO"):
        require_local_services(config)


def test_verification_refuses_azure_even_with_local_endpoints(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "configured")
    with pytest.raises(ValueError, match="Azure must be unset"):
        require_local_services(settings())
