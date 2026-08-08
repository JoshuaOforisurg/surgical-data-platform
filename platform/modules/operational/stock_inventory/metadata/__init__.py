"""PostgreSQL-backed operational metadata for Stock Inventory."""

from metadata.repository import PostgresMetadataRepository, metadata_repository_from_settings

__all__ = ["PostgresMetadataRepository", "metadata_repository_from_settings"]
