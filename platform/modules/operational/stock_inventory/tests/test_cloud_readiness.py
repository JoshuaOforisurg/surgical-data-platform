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
    monkeypatch.delenv("STOCK_PIPELINE_SOURCE_DIR", raising=False)
    monkeypatch.delenv("SURGEON_PREFERENCE_GOLD_PATH", raising=False)
    monkeypatch.delenv("STOCK_DASHBOARD_STORAGE_MODE", raising=False)

    result = run_checks()

    assert result.status == "not_cloud_ready"
    checks = {check["name"]: check for check in result.checks}
    assert checks["object_store.endpoint_remote"]["passed"] is False
    assert checks["object_store.credentials_not_defaults"]["passed"] is False
    assert checks["dashboard.object_store_mode"]["passed"] is False


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

    result = run_checks(require_cross_pipeline=True)

    assert result.status == "cloud_ready"
    assert result.failure_count == 0
