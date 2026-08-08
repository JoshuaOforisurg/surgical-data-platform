from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any

from config.settings import ObjectStoreSettings


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().strip("\"'") or None


def normalise_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        clean_key = re.sub(r"[^0-9A-Za-z_]", "_", str(key))
        clean[clean_key] = str(value)
    return clean


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type_for(path: str | Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


class ObjectStoreClient:
    """Select Azure Blob in cloud environments and S3/MinIO otherwise."""

    def __new__(cls, settings: ObjectStoreSettings):
        if cls is ObjectStoreClient:
            if _env_value("AZURE_STORAGE_CONNECTION_STRING"):
                return AzureBlobObjectStoreClient(settings)
            return S3ObjectStoreClient(settings)
        return super().__new__(cls)


class S3ObjectStoreClient:
    def __init__(self, settings: ObjectStoreSettings):
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:
            raise ImportError("boto3 is required for MinIO/S3 object storage support") from exc

        self.settings = settings
        self.bucket = settings.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
            use_ssl=settings.secure,
        )

    def wait_until_ready(self, attempts: int = 20, delay_seconds: float = 2.0) -> None:
        last_error: Exception | None = None
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
        if not any(bucket.get("Name") == self.bucket for bucket in buckets):
            self.client.create_bucket(Bucket=self.bucket)

    def upload_file(
        self,
        local_path: str | Path,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        path = Path(local_path)
        self.client.upload_file(
            Filename=str(path),
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type or content_type_for(path),
                "Metadata": normalise_metadata(metadata),
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

    def get_text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def list_objects(self, prefix: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"


class AzureBlobObjectStoreClient:
    """Azure Blob implementation of the stock object-store interface."""

    def __init__(self, settings: ObjectStoreSettings):
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise ImportError("azure-storage-blob is required for Azure Blob support") from exc

        connection_string = _env_value("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required for Azure Blob mode")

        self.settings = settings
        self.bucket = _env_value("AZURE_CONTAINER_NAME") or settings.bucket
        self.client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.client.get_container_client(self.bucket)

    def wait_until_ready(self, attempts: int = 20, delay_seconds: float = 2.0) -> None:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                self.ensure_bucket()
                self.container_client.get_container_properties()
                return
            except Exception as exc:
                last_error = exc
                time.sleep(delay_seconds)
        raise RuntimeError(f"Azure Blob storage is not reachable: {last_error}")

    def ensure_bucket(self) -> None:
        from azure.core.exceptions import ResourceExistsError

        try:
            self.container_client.create_container()
        except ResourceExistsError:
            return

    def upload_file(
        self,
        local_path: str | Path,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        from azure.storage.blob import ContentSettings

        path = Path(local_path)
        with path.open("rb") as data:
            self.container_client.get_blob_client(key).upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type or content_type_for(path)),
                metadata=normalise_metadata(metadata),
            )
        return self.uri(key)

    def put_text(self, key: str, text: str, content_type: str = "text/plain") -> str:
        from azure.storage.blob import ContentSettings

        self.container_client.get_blob_client(key).upload_blob(
            text.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return self.uri(key)

    def get_text(self, key: str) -> str:
        return self.container_client.get_blob_client(key).download_blob().readall().decode("utf-8")

    def list_objects(self, prefix: str) -> list[str]:
        return [blob.name for blob in self.container_client.list_blobs(name_starts_with=prefix)]

    def uri(self, key: str) -> str:
        return f"azblob://{self.bucket}/{key}"
