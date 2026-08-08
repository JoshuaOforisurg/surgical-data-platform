from __future__ import annotations

import sys
from types import SimpleNamespace

from metadata.repository import MIGRATION_PATH, metadata_repository_from_settings
from config.settings import PostgresSettings, load_settings
from metadata.repository import PostgresMetadataRepository


def test_postgres_settings_are_optional(monkeypatch):
    for name in ("STOCK_DB_HOST", "STOCK_DB_USER", "STOCK_DB_PASSWORD", "STOCK_DB_NAME"):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.postgres is None
    assert metadata_repository_from_settings(settings) is None


def test_postgres_settings_load_dedicated_stock_database(monkeypatch):
    monkeypatch.setenv("STOCK_DB_HOST", "stock-postgres")
    monkeypatch.setenv("STOCK_DB_PORT", "5432")
    monkeypatch.setenv("STOCK_DB_USER", "stock_inventory_app")
    monkeypatch.setenv("STOCK_DB_PASSWORD", "test-password")
    monkeypatch.setenv("STOCK_DB_NAME", "stock_inventory")

    settings = load_settings()

    assert settings.postgres is not None
    assert settings.postgres.host == "stock-postgres"
    assert settings.postgres.database == "stock_inventory"
    assert settings.postgres.password == "test-password"
    assert settings.postgres.sslmode == "prefer"


def test_initial_migration_defines_metadata_contract():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    for table in (
        "pipeline_runs",
        "pipeline_stages",
        "ingested_files",
        "quality_gate_results",
        "published_artifacts",
    ):
        assert f"stock_metadata.{table}" in migration


def test_repository_passes_special_character_password_as_connection_argument(monkeypatch):
    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=fake_connect))
    repository = PostgresMetadataRepository(
        PostgresSettings(
            host="database.example",
            port=5432,
            user="stock_inventory_app",
            password="spaces ' quotes = remain intact",
            database="stock_inventory",
        )
    )

    repository._connect()

    assert captured["password"] == "spaces ' quotes = remain intact"
    assert captured["sslmode"] == "prefer"
