from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path
from typing import BinaryIO, Iterable, Optional

import boto3
from botocore.client import Config

from config.settings import MinIOSettings


class ObjectStoreClient:
    """Small S3-compatible client used for MinIO locally and Azure-compatible swaps later."""

    def __init__(self, settings: MinIOSettings):
        self.settings = settings
        self.bucket = settings.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def wait_until_ready(self, attempts: int = 20, delay_seconds: float = 2.0) -> None:
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                self.client.list_buckets()
                self.ensure_bucket()
                return
            except Exception as exc:
                last_error = exc
                time.sleep(delay_seconds)
        raise RuntimeError(f"Object store is not reachable: {last_error}")

    def ensure_bucket(self) -> None:
        buckets = self.client.list_buckets().get("Buckets", [])
        if not any(bucket["Name"] == self.bucket for bucket in buckets):
            self.client.create_bucket(Bucket=self.bucket)

    def upload_file(
        self,
        local_path: str | Path,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        self.client.upload_file(
            Filename=str(local_path),
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": metadata or {},
            },
        )
        return self.uri(key)

    def put_text(self, key: str, text: str, content_type: str = "text/plain") -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType=content_type,
        )
        return self.uri(key)

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=metadata or {},
        )
        return self.uri(key)

    def get_text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def download_file(self, key: str, local_path: str | Path) -> Path:
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))
        return path

    def list_objects(self, prefix: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def latest_key(self, prefix: str, suffix: str = "") -> Optional[str]:
        keys = [key for key in self.list_objects(prefix) if key.endswith(suffix)]
        return sorted(keys)[-1] if keys else None

    def stat_object(self, key: str) -> dict:
        return self.client.head_object(Bucket=self.bucket, Key=key)

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_from_text(text: str) -> bytes:
    return text.encode("utf-8")
