import io
import uuid
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Create a boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name="us-east-1",
    )


def ensure_bucket_exists() -> None:
    """Create the S3 bucket if it doesn't already exist."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        logger.info(f"Bucket '{settings.S3_BUCKET_NAME}' already exists.")
    except ClientError:
        client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
        logger.info(f"Created bucket '{settings.S3_BUCKET_NAME}'.")


def upload_file(file_content: bytes, original_filename: str, user_id: str) -> str:
    """
    Upload a file to S3/MinIO.
    Returns the object key (path) used to store the file.
    """
    ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "jpg"
    object_key = f"bills/{user_id}/{uuid.uuid4()}.{ext}"

    client = _get_s3_client()
    client.upload_fileobj(
        io.BytesIO(file_content),
        settings.S3_BUCKET_NAME,
        object_key,
        ExtraArgs={"ContentType": f"image/{ext}"},
    )
    logger.info(f"Uploaded file to s3://{settings.S3_BUCKET_NAME}/{object_key}")
    return object_key


def generate_presigned_url(object_key: str) -> str:
    """Generate a time-limited presigned URL for accessing a stored file."""
    # Use the public URL so the signed URL is accessible from outside Docker
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_PUBLIC_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name="us-east-1",
    )
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": object_key},
        ExpiresIn=settings.SIGNED_URL_EXPIRY,
    )
    return url


def delete_file(object_key: str) -> None:
    """Delete a file from S3/MinIO."""
    client = _get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=object_key)
    logger.info(f"Deleted s3://{settings.S3_BUCKET_NAME}/{object_key}")
