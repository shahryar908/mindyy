import io
import os
from typing import BinaryIO
from uuid import UUID, uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

_s3_client = None


def s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )
    return _s3_client


def put_object(key: str, body: BinaryIO, content_type: str) -> None:
    s3_client().upload_fileobj(
        Fileobj=body,
        Bucket=S3_BUCKET,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def download_object(key: str) -> bytes:
    buf = io.BytesIO()
    s3_client().download_fileobj(Bucket=S3_BUCKET, Key=key, Fileobj=buf)
    return buf.getvalue()


def delete_object(key: str) -> None:
    try:
        s3_client().delete_object(Bucket=S3_BUCKET, Key=key)
    except ClientError:
        pass


def generate_presigned_get_url(key: str, expires_in: int = 3600) -> str:
    return s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


def build_object_key(user_id: UUID, kind: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{kind}/{user_id}/{uuid4()}.{ext}"
