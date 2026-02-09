"""MinIO storage helper for MinIO service"""

import os
from typing import List

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")

_minio_client = None


def get_minio_client():
    """Get or create MinIO client"""
    global _minio_client
    if _minio_client is None:
        from minio import Minio

        _minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
    return _minio_client


def get_minio_status() -> str:
    """Check MinIO connection status"""
    try:
        client = get_minio_client()
        client.list_buckets()
        return "connected"
    except Exception as e:
        return f"error: {str(e)}"


def list_buckets() -> List[str]:
    """List all buckets"""
    client = get_minio_client()
    return [b.name for b in client.list_buckets()]


def ensure_bucket(bucket_name: str) -> bool:
    """Ensure bucket exists"""
    client = get_minio_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    return True


def upload_file(bucket_name: str, object_name: str, file_path: str) -> bool:
    """Upload file to MinIO"""
    client = get_minio_client()
    client.fput_object(bucket_name, object_name, file_path)
    return True


def download_file(bucket_name: str, object_name: str, file_path: str) -> bool:
    """Download file from MinIO"""
    client = get_minio_client()
    client.fget_object(bucket_name, object_name, file_path)
    return True
