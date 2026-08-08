from __future__ import annotations

import os

from config.settings import PostgresSettings, load_settings
from metadata.repository import PostgresMetadataRepository


def main() -> None:
    settings = load_settings()
    if settings.postgres is None:
        raise RuntimeError("STOCK_DB_HOST, STOCK_DB_USER, STOCK_DB_PASSWORD, and STOCK_DB_NAME are required")
    runtime_settings = settings.postgres
    migration_settings = PostgresSettings(
        host=os.getenv("STOCK_MIGRATION_DB_HOST", "").strip() or runtime_settings.host,
        port=int(os.getenv("STOCK_MIGRATION_DB_PORT", "").strip() or runtime_settings.port),
        user=os.getenv("STOCK_MIGRATION_DB_USER", "").strip() or runtime_settings.user,
        password=os.getenv("STOCK_MIGRATION_DB_PASSWORD", "").strip() or runtime_settings.password,
        database=os.getenv("STOCK_MIGRATION_DB_NAME", "").strip() or runtime_settings.database,
        sslmode=os.getenv("STOCK_MIGRATION_DB_SSLMODE", "").strip() or runtime_settings.sslmode,
    )
    repository = PostgresMetadataRepository(migration_settings)
    repository.migrate()
    repository.grant_runtime_access(runtime_settings.user)
    print("Stock Inventory metadata migration completed.")


if __name__ == "__main__":
    main()
