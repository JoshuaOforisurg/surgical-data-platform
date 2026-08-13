"""Compatibility imports for the platform shared object-store implementation."""

import sys
from pathlib import Path

try:
    import shared.storage.object_store  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "shared":
        raise
    platform_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(platform_root))

from shared.storage.object_store import (
    AzureBlobObjectStoreClient,
    ObjectStoreClient,
    S3ObjectStoreClient,
    bytes_from_text,
    content_type_for,
    normalise_metadata,
    sha256_file,
)

__all__ = [
    "AzureBlobObjectStoreClient",
    "ObjectStoreClient",
    "S3ObjectStoreClient",
    "bytes_from_text",
    "content_type_for",
    "normalise_metadata",
    "sha256_file",
]
