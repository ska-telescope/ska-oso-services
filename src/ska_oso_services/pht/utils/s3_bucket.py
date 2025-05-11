import os
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.client import BaseClient, Config

PRESIGNED_URL_EXPIRY_TIME = int(os.getenv("PRESIGNED_URL_EXPIRY_TIME", "60"))


class S3Method(str, Enum):
    GET = "get_object"
    PUT = "put_object"
    DELETE = "delete_object"


@dataclass(frozen=True)
class S3Config:
    access_key: str = os.getenv("AWS_SERVER_PUBLIC_KEY", "AWS_SERVER_PUBLIC_KEY")
    secret_key: str = os.getenv("AWS_SERVER_SECRET_KEY", "AWS_SERVER_SECRET_KEY")
    bucket: str = os.getenv("AWS_PHT_BUCKET_NAME", "AWS_PHT_BUCKET_NAME")
    region: str = os.getenv("AWS_REGION", "eu-west-2")
    expiry: int = PRESIGNED_URL_EXPIRY_TIME


def get_aws_client(config: S3Config = S3Config()) -> BaseClient:
    return boto3.client(
        "s3",
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_url(
    key: str,
    method: S3Method,
    client: BaseClient,
    config: S3Config = S3Config(),
) -> str:
    return client.generate_presigned_url(
        ClientMethod=method.value,
        Params={"Bucket": config.bucket, "Key": key},
        ExpiresIn=config.expiry,
    )


def create_presigned_url_upload_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 upload URL for the given filename.
    """
    return generate_presigned_url(key, S3Method.PUT, client, S3Config(expiry=expiry))


def create_presigned_url_download_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 download URL for the given filename.
    """
    return generate_presigned_url(key, S3Method.GET, client, S3Config(expiry=expiry))


def create_presigned_url_delete_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.
    """
    return generate_presigned_url(key, S3Method.DELETE, client, S3Config(expiry=expiry))
