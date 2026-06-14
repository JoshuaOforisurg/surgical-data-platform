import os
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from minio import Minio
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _calculate_local_sha256(file_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Calculates SHA256 checksum of a local file in chunks to optimize memory."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)
    return sha.hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry_error_callback=lambda _: None  # Suppress retry errors and return None
)
def drop_to_landing_zone(
        source_file_path: str,
        minio_endpoint: str,
        minio_access_key: str,
        minio_secret_key: str,
        minio_bucket: str = "surgeon_preference",
        minio_landing_prefix: str = "landing/",
        secure: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        max_file_size: int = MAX_FILE_SIZE
) -> Optional[str]:
    """
    Upload a raw file into the MinIO landing zone with retry logic, validation,
    and pre-calculated SHA256 metadata support to optimize Strategy B ingestion.
    """

    # Validate source file
    if not os.path.isfile(source_file_path):
        logger.error("Source file does not exist: %s", source_file_path)
        return None

    # Validate file size
    file_size = os.path.getsize(source_file_path)
    if file_size > max_file_size:
        logger.error(
            "File '%s' exceeds maximum size of %d MB. Actual size: %d MB",
            source_file_path,
            max_file_size / (1024 * 1024),
            file_size / (1024 * 1024)
        )
        return None

    try:
        # Create MinIO client
        client = Minio(
            endpoint=minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=secure
        )

        # Validate credentials (pre-flight check)
        try:
            client.list_buckets()
        except Exception:
            logger.error("Invalid MinIO credentials or endpoint.")
            return None

        # Create unique object name
        file_name = os.path.basename(source_file_path)
        # FIXED: Replaced deprecated UTC call with modern timezone structure
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        object_name = f"{minio_landing_prefix}{timestamp}_{file_name}"

        # Determine content type
        content_type = "application/octet-stream"  # Default binary
        if file_name.endswith(('.json', '.csv', '.txt', '.xml')):
            content_type = "text/plain"
        elif file_name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            content_type = "image/jpeg" if file_name.endswith(('.jpg', '.jpeg')) else "image/png"
        elif file_name.endswith(('.pdf',)):
            content_type = "application/pdf"

        # Ensure bucket exists
        if not client.bucket_exists(minio_bucket):
            logger.info("Bucket '%s' does not exist. Creating bucket.", minio_bucket)
            client.make_bucket(minio_bucket)
            logger.info("Bucket '%s' created successfully.", minio_bucket)

        # ------------------------------------------------------------
        # STRATEGY B ENHANCEMENT: Pre-calculate SHA256 checksum
        # ------------------------------------------------------------
        upload_metadata = metadata.copy() if metadata else {}

        # Calculate local file hash before pushing
        logger.info("Calculating SHA256 hash for local file: %s", file_name)
        file_hash = _calculate_local_sha256(source_file_path)

        # Inject custom header standard recognized by modern S3 ecosystems
        upload_metadata["checksum-sha256"] = file_hash

        # Upload file (fput_object handles multipart chunking safely under the hood)
        logger.info("Uploading file '%s' (%d MB) to MinIO...", file_name, file_size / (1024 * 1024))
        client.fput_object(
            bucket_name=minio_bucket,
            object_name=object_name,
            file_path=source_file_path,
            content_type=content_type,
            metadata=upload_metadata
        )

        uploaded_path = f"s3://{minio_bucket}/{object_name}"
        logger.info("Successfully uploaded file to landing zone: %s", uploaded_path)
        return uploaded_path

    except Exception:
        logger.exception("Failed to upload file '%s' to MinIO", source_file_path)
        return None
