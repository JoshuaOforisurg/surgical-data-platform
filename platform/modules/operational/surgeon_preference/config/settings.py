from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class MinIOSettings:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    landing_prefix: str = "landing"
    bronze_prefix: str = "bronze"
    silver_prefix: str = "silver"
    gold_prefix: str = "gold"
    secure: bool = False


@dataclass(frozen=True)
class PostgresSettings:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def psycopg2_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )

    @property
    def sqlalchemy_uri(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class PipelineSettings:
    environment: str
    project_root: Path
    default_input_path: Path
    synthetic_record_count: int
    synthetic_output_mode: str
    synthetic_file_formats: str
    minio: MinIOSettings
    postgres: Optional[PostgresSettings]


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def load_settings() -> PipelineSettings:
    project_root = Path(__file__).resolve().parents[1]

    minio_endpoint = _env("MINIO_ENDPOINT", "http://localhost:9000")
    minio_secure = str(_env("MINIO_SECURE", "false")).lower() in {"1", "true", "yes"}

    postgres_host = _env("POSTGRES_HOST") or _env("DB_HOST")
    postgres_user = _env("POSTGRES_USER") or _env("DB_USER")
    postgres_password = _env("POSTGRES_PASSWORD") or _env("DB_PASSWORD")
    postgres_database = _env("POSTGRES_DB") or _env("DB_NAME")
    postgres_port = int(_env("POSTGRES_PORT") or _env("DB_PORT") or "5432")

    postgres = None
    if postgres_host and postgres_user and postgres_password and postgres_database:
        postgres = PostgresSettings(
            host=postgres_host,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database=postgres_database,
        )

    return PipelineSettings(
        environment=_env("ENVIRONMENT", "local") or "local",
        project_root=project_root,
        default_input_path=Path(
            _env(
                "PIPELINE_INPUT_PATH",
                str(project_root / "generate_synthetic_data/output/master_preferences.json"),
            )
        ),
        synthetic_record_count=int(_env("SYNTHETIC_RECORD_COUNT", "1000") or "1000"),
        synthetic_output_mode=_env("SYNTHETIC_OUTPUT_MODE", "master") or "master",
        synthetic_file_formats=_env("SYNTHETIC_FILE_FORMATS", "json,csv") or "json,csv",
        minio=MinIOSettings(
            endpoint=minio_endpoint or "http://localhost:9000",
            access_key=_env("MINIO_ROOT_USER") or _env("MINIO_ACCESS_KEY") or "minioadmin",
            secret_key=_env("MINIO_ROOT_PASSWORD") or _env("MINIO_SECRET_KEY") or "minioadmin",
            bucket=_env("MINIO_BUCKET", "surgical-data") or "surgical-data",
            landing_prefix=_env("MINIO_LANDING_PREFIX", "landing") or "landing",
            bronze_prefix=_env("MINIO_BRONZE_PREFIX", "bronze") or "bronze",
            silver_prefix=_env("MINIO_SILVER_PREFIX", "silver") or "silver",
            gold_prefix=_env("MINIO_GOLD_PREFIX", "gold") or "gold",
            secure=minio_secure,
        ),
        postgres=postgres,
    )
