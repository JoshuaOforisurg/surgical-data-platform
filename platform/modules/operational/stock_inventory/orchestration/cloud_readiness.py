from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.settings import ObjectStoreSettings, load_settings


LOCAL_ENDPOINT_HOSTS = {"localhost", "127.0.0.1", "::1", "stock-minio"}
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1", "stock-postgres"}
TLS_DATABASE_MODES = {"require", "verify-ca", "verify-full"}
DEFAULT_CREDENTIALS = {
    ("minioadmin", "minioadmin"),
    ("", ""),
}


@dataclass(frozen=True)
class CloudReadinessCheck:
    name: str
    passed: bool
    severity: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CloudReadinessResult:
    status: str
    check_count: int
    failure_count: int
    warning_count: int
    checks: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def object_store_endpoint_is_remote(settings: ObjectStoreSettings) -> bool:
    parsed = urlparse(settings.endpoint)
    host = parsed.hostname or settings.endpoint
    return host not in LOCAL_ENDPOINT_HOSTS


def object_store_credentials_are_not_defaults(settings: ObjectStoreSettings) -> bool:
    credentials = (settings.access_key.strip(), settings.secret_key.strip())
    return all(credentials) and credentials not in DEFAULT_CREDENTIALS


def existing_path_from_env(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and Path(value).exists())


def azure_blob_configured() -> bool:
    return bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip())


def postgres_configuration() -> tuple[str, str, str, str]:
    return tuple(
        os.getenv(name, "").strip()
        for name in ("STOCK_DB_HOST", "STOCK_DB_USER", "STOCK_DB_PASSWORD", "STOCK_DB_NAME")
    )


def run_checks(require_cross_pipeline: bool = False) -> CloudReadinessResult:
    settings = load_settings()
    dashboard_mode = os.getenv("STOCK_DASHBOARD_STORAGE_MODE", "local").strip().lower()
    azure_mode = azure_blob_configured()
    container_name = os.getenv("AZURE_CONTAINER_NAME", "").strip()
    database_config = postgres_configuration()
    database_host = database_config[0].lower()
    database_sslmode = os.getenv("STOCK_DB_SSLMODE", "").strip().lower()

    checks = [
        CloudReadinessCheck(
            name="object_store.cloud_provider_configured",
            passed=azure_mode or object_store_endpoint_is_remote(settings.object_store),
            severity="error",
            message="Azure Blob or a remote S3-compatible object store is configured.",
        ),
        CloudReadinessCheck(
            name="object_store.credentials_configured",
            passed=azure_mode or object_store_credentials_are_not_defaults(settings.object_store),
            severity="error",
            message="Cloud object-store credentials are configured and are not local defaults.",
        ),
        CloudReadinessCheck(
            name="object_store.container_configured",
            passed=bool(container_name) if azure_mode else bool(settings.object_store.bucket.strip()),
            severity="error",
            message="Object-store container or bucket is configured.",
        ),
        CloudReadinessCheck(
            name="object_store.root_prefix_configured",
            passed=bool(settings.object_store.root_prefix.strip()),
            severity="error",
            message="Object store root prefix is configured for run isolation.",
        ),
        CloudReadinessCheck(
            name="dashboard.object_store_mode",
            passed=dashboard_mode == "object_store",
            severity="error",
            message="Streamlit dashboard is configured to read published Gold artifacts from object storage.",
        ),
        CloudReadinessCheck(
            name="database.configuration_complete",
            passed=all(database_config),
            severity="error",
            message="Managed PostgreSQL host, user, password, and database are configured.",
        ),
        CloudReadinessCheck(
            name="database.managed_host",
            passed=bool(database_host) and database_host not in LOCAL_DATABASE_HOSTS,
            severity="error",
            message="PostgreSQL points to a managed host rather than a local Docker service.",
        ),
        CloudReadinessCheck(
            name="database.tls_required",
            passed=database_sslmode in TLS_DATABASE_MODES,
            severity="error",
            message="PostgreSQL transport encryption is explicitly required.",
        ),
        CloudReadinessCheck(
            name="pipeline.source_dir_configurable",
            passed=bool(os.getenv("STOCK_PIPELINE_SOURCE_DIR", "").strip()),
            severity="warning",
            message="Pipeline source directory is provided through STOCK_PIPELINE_SOURCE_DIR.",
        ),
        CloudReadinessCheck(
            name="cross_pipeline.preference_gold_path",
            passed=existing_path_from_env("SURGEON_PREFERENCE_GOLD_PATH"),
            severity="error" if require_cross_pipeline else "warning",
            message="Surgeon preference Gold handoff path exists for cross-pipeline readiness analytics.",
        ),
    ]

    failures = [check for check in checks if check.severity == "error" and not check.passed]
    warnings = [check for check in checks if check.severity == "warning" and not check.passed]
    status = "cloud_ready" if not failures else "not_cloud_ready"
    return CloudReadinessResult(
        status=status,
        check_count=len(checks),
        failure_count=len(failures),
        warning_count=len(warnings),
        checks=[check.to_dict() for check in checks],
    )


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check whether the stock inventory module is cloud-ready.")
    parser.add_argument(
        "--require-cross-pipeline",
        action="store_true",
        help="Treat missing SURGEON_PREFERENCE_GOLD_PATH as a blocking error.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_checks(require_cross_pipeline=args.require_cross_pipeline)
    print(json.dumps(result.to_dict(), indent=2))
    if result.failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
