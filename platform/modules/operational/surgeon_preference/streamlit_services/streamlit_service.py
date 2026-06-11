import os
import time
from abc import ABC, abstractmethod
import boto3
from botocore.client import Config
from azure.storage.blob import BlobServiceClient


# 1. Abstract Base Class (The Interface)
class StorageClient(ABC):
    @abstractmethod
    def list_objects(self, prefix: str) -> list[str]:
        """Returns a clean list of string file paths/keys."""
        pass

    @abstractmethod
    def download_file(self, key: str, local_path: str) -> None:
        """Downloads a file to the local system."""
        pass


# 2. Local MinIO Implementation
class MinIOClient(StorageClient):
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT")
        self.access_key = os.getenv("MINIO_ROOT_USER")
        self.secret_key = os.getenv("MINIO_ROOT_PASSWORD")
        self.bucket = os.getenv("MINIO_BUCKET", "surgical-data")

        if not self.endpoint:
            raise ValueError("MINIO_ENDPOINT is required for local MinIO mode")

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1"
        )
        self._wait_for_minio()
        self._ensure_bucket()

    def _wait_for_minio(self):
        # Kept strictly for local docker-compose startup synchronisation
        for _ in range(10):
            try:
                self.client.list_buckets()
                return
            except Exception:
                time.sleep(2)
        raise RuntimeError("Local MinIO not reachable")

    def _ensure_bucket(self):
        try:
            buckets = self.client.list_buckets()
            if not any(b["Name"] == self.bucket for b in buckets.get("Buckets", [])):
                self.client.create_bucket(Bucket=self.bucket)
        except Exception as e:
            raise RuntimeError(f"Local bucket setup failed: {e}")

    def list_objects(self, prefix: str) -> list[str]:
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        contents = resp.get("Contents", [])
        return [item["Key"] for item in contents]  # Standardised to return plain strings

    def download_file(self, key: str, local_path: str) -> None:
        self.client.download_file(self.bucket, key, local_path)


# 3. Azure Production Implementation
class AzureBlobStorageClient(StorageClient):
    def __init__(self):
        self.conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = os.getenv("AZURE_CONTAINER_NAME", "surgical-data")

        if not self.conn_str:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required for Azure mode")

        self.blob_service_client = BlobServiceClient.from_connection_string(self.conn_str)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
        # Note: No slow health check loops or auto-creation blocks here for cloud production safely.

    def list_objects(self, prefix: str) -> list[str]:
        blobs = self.container_client.list_blobs(name_starts_with=prefix)
        return [blob.name for blob in blobs]  # Standardised to return plain strings

    def download_file(self, key: str, local_path: str) -> None:
        blob_client = self.container_client.get_blob_client(key)
        with open(local_path, "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())


# 4. Factory Function (The Magic Switcher)
def get_storage_client() -> StorageClient:
    """
    Dynamically returns the Azure client if the Azure connection string is present.
    Otherwise, defaults to the local MinIO client.
    """
    if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        return AzureBlobStorageClient()
    return MinIOClient()
