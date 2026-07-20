from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from config.paths import MODULE_ROOT, SYNTHETIC_GENERATED_DIR


@dataclass(frozen=True)
class ObjectStoreSettings:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    root_prefix: str


@dataclass(frozen=True)
class PipelineSettings:
    project_root: Path
    default_source_dir: Path
    object_store: ObjectStoreSettings


def env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = env_value(name, "true" if default else "false").lower()
    return value in {"1", "true", "yes", "y"}


def load_settings() -> PipelineSettings:
    return PipelineSettings(
        project_root=MODULE_ROOT,
        default_source_dir=Path(env_value("STOCK_PIPELINE_SOURCE_DIR", str(SYNTHETIC_GENERATED_DIR))),
        object_store=ObjectStoreSettings(
            endpoint=env_value("MINIO_ENDPOINT", "http://localhost:9000"),
            access_key=env_value("MINIO_ROOT_USER", env_value("MINIO_ACCESS_KEY", "minioadmin")),
            secret_key=env_value("MINIO_ROOT_PASSWORD", env_value("MINIO_SECRET_KEY", "minioadmin")),
            bucket=env_value("MINIO_BUCKET", "stock-inventory"),
            secure=env_bool("MINIO_SECURE", False),
            root_prefix=env_value("MINIO_ROOT_PREFIX", "stock_inventory"),
        ),
    )
