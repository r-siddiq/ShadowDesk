import os
from typing import BinaryIO, List, Optional

from minio import Minio

CLUSTER_B_HOST = os.getenv("MINIO_ENDPOINT", "localhost:9000")
CLUSTER_B_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
CLUSTER_B_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")

_client: Optional[Minio] = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            CLUSTER_B_HOST,
            access_key=CLUSTER_B_ACCESS_KEY,
            secret_key=CLUSTER_B_SECRET_KEY,
            secure=False,
        )
    return _client


def reset_client():
    global _client
    _client = None


def list_buckets() -> List[str]:
    client = get_client()
    return [bucket.name for bucket in client.list_buckets()]


def bucket_exists(bucket_name: str) -> bool:
    client = get_client()
    return client.bucket_exists(bucket_name)


def create_bucket(bucket_name: str):
    client = get_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_file(
    bucket_name: str,
    object_name: str,
    file_path: str,
    content_type: Optional[str] = None,
):
    client = get_client()
    client.fput_object(bucket_name, object_name, file_path, content_type=content_type)


def upload_data(
    bucket_name: str,
    object_name: str,
    data: BinaryIO,
    length: int,
    content_type: Optional[str] = None,
):
    client = get_client()
    client.put_object(bucket_name, object_name, data, length, content_type=content_type)


def download_file(bucket_name: str, object_name: str, file_path: str):
    client = get_client()
    client.fget_object(bucket_name, object_name, file_path)


def get_object(bucket_name: str, object_name: str) -> bytes:
    client = get_client()
    response = client.get_object(bucket_name, object_name)
    return response.read()


def list_objects(bucket_name: str, prefix: str = "") -> List[str]:
    client = get_client()
    return [obj.object_name for obj in client.list_objects(bucket_name, prefix=prefix)]


def remove_object(bucket_name: str, object_name: str):
    client = get_client()
    client.remove_object(bucket_name, object_name)


def remove_bucket(bucket_name: str):
    client = get_client()
    client.remove_bucket(bucket_name)
