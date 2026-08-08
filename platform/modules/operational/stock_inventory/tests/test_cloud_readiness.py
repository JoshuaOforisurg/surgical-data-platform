from __future__ import annotations

from orchestration.cloud_readiness import run_checks


def test_cloud_readiness_blocks_local_defaults(monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("MINIO_ROOT_USER", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.delenv("MINIO_BUCKET", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PREFIX", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_CONTAINER_NAME", raising=False)
    monkeypatch.delenv("STOCK_PIPELINE_SOURCE_DIR", raising=False)
    monkeypatch.delenv("SURGEON_PREFERENCE_GOLD_PATH", raising=False)
    monkeypatch.delenv("STOCK_DASHBOARD_STORAGE_MODE", raising=False)
    monkeypatch.delenv("STOCK_DB_HOST", raising=False)
    monkeypatch.delenv("STOCK_DB_USER", raising=False)
    monkeypatch.delenv("STOCK_DB_PASSWORD", raising=False)
    monkeypatch.delenv("STOCK_DB_NAME", raising=False)
    monkeypatch.delenv("STOCK_DB_SSLMODE", raising=False)

    result = run_checks()

    assert result.status == "not_cloud_ready"
    checks = {check["name"]: check for check in result.checks}
    assert checks["object_store.cloud_provider_configured"]["passed"] is False
    assert checks["object_store.credentials_configured"]["passed"] is False
    assert checks["dashboard.object_store_mode"]["passed"] is False
    assert checks["database.configuration_complete"]["passed"] is False
    assert checks["database.managed_host"]["passed"] is False
    assert checks["database.tls_required"]["passed"] is False


def test_cloud_readiness_passes_remote_object_store_contract(monkeypatch, tmp_path):
    preference_gold = tmp_path / "gold_operational_preference_cards.json"
    preference_gold.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("MINIO_ENDPOINT", "https://s3.eu-west-2.amazonaws.com")
    monkeypatch.setenv("MINIO_ROOT_USER", "cloud-access-key")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "cloud-secret-key")
    monkeypatch.setenv("MINIO_BUCKET", "surgical-platform-prod")
    monkeypatch.setenv("MINIO_ROOT_PREFIX", "stock_inventory/prod")
    monkeypatch.setenv("STOCK_PIPELINE_SOURCE_DIR", "/mnt/source")
    monkeypatch.setenv("SURGEON_PREFERENCE_GOLD_PATH", str(preference_gold))
    monkeypatch.setenv("STOCK_DASHBOARD_STORAGE_MODE", "object_store")
    monkeypatch.setenv("STOCK_DB_HOST", "stock-prod.postgres.database.azure.com")
    monkeypatch.setenv("STOCK_DB_USER", "stock_inventory_app")
    monkeypatch.setenv("STOCK_DB_PASSWORD", "test-only-password")
    monkeypatch.setenv("STOCK_DB_NAME", "stock_inventory")
    monkeypatch.setenv("STOCK_DB_SSLMODE", "require")

    result = run_checks(require_cross_pipeline=True)

    assert result.status == "cloud_ready"
    assert result.failure_count == 0


def test_cloud_readiness_passes_azure_blob_contract(monkeypatch):
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=stockprod;AccountKey=placeholder;EndpointSuffix=core.windows.net",
    )
    monkeypatch.setenv("AZURE_CONTAINER_NAME", "stock-inventory")
    monkeypatch.setenv("MINIO_ROOT_PREFIX", "stock_inventory/prod")
    monkeypatch.setenv("STOCK_PIPELINE_SOURCE_DIR", "synthetic_data/generated")
    monkeypatch.setenv("STOCK_DASHBOARD_STORAGE_MODE", "object_store")
    monkeypatch.setenv("STOCK_DB_HOST", "stock-prod.postgres.database.azure.com")
    monkeypatch.setenv("STOCK_DB_USER", "stock_inventory_app")
    monkeypatch.setenv("STOCK_DB_PASSWORD", "test-only-password")
    monkeypatch.setenv("STOCK_DB_NAME", "stock_inventory")
    monkeypatch.setenv("STOCK_DB_SSLMODE", "require")

    result = run_checks()

    assert result.status == "cloud_ready"
    assert result.failure_count == 0


def test_cloud_readiness_rejects_local_postgres(monkeypatch):
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=stockprod;AccountKey=placeholder;EndpointSuffix=core.windows.net",
    )
    monkeypatch.setenv("AZURE_CONTAINER_NAME", "stock-inventory")
    monkeypatch.setenv("MINIO_ROOT_PREFIX", "stock_inventory/prod")
    monkeypatch.setenv("STOCK_DASHBOARD_STORAGE_MODE", "object_store")
    monkeypatch.setenv("STOCK_DB_HOST", "stock-postgres")
    monkeypatch.setenv("STOCK_DB_USER", "stock_inventory_app")
    monkeypatch.setenv("STOCK_DB_PASSWORD", "test-only-password")
    monkeypatch.setenv("STOCK_DB_NAME", "stock_inventory")
    monkeypatch.setenv("STOCK_DB_SSLMODE", "require")

    result = run_checks()

    checks = {check["name"]: check for check in result.checks}
    assert result.status == "not_cloud_ready"
    assert checks["database.configuration_complete"]["passed"] is True
    assert checks["database.managed_host"]["passed"] is False
