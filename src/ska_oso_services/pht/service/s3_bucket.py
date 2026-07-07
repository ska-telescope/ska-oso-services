import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import boto3
from botocore.client import BaseClient, Config

PRESIGNED_URL_EXPIRY_TIME = int(os.getenv("PRESIGNED_URL_EXPIRY_TIME", "60"))


class S3Method(str, Enum):
    GET = "get_object"
    PUT = "put_object"
    DELETE = "delete_object"


@dataclass(frozen=True)
class S3Config:
    access_key: str | None = os.getenv("AWS_SERVER_PUBLIC_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key: str | None = os.getenv("AWS_SERVER_SECRET_KEY") or os.getenv(
        "AWS_SECRET_ACCESS_KEY"
    )
    session_token: str | None = os.getenv("AWS_SESSION_TOKEN")
    bucket: str = os.getenv("AWS_PHT_BUCKET_NAME", "AWS_PHT_BUCKET_NAME")
    region: str = os.getenv("AWS_REGION", "eu-west-2")
    expiry: int = PRESIGNED_URL_EXPIRY_TIME


def get_aws_client(config: S3Config = S3Config()) -> BaseClient:
    client_kwargs: dict[str, Any] = {
        "region_name": config.region,
        "config": Config(signature_version="s3v4"),
    }

    # If credentials are not explicitly provided, boto3 falls back to
    # the default AWS credential chain (for example EKS Pod Identity).
    if config.access_key and config.secret_key:
        client_kwargs["aws_access_key_id"] = config.access_key
        client_kwargs["aws_secret_access_key"] = config.secret_key
        if config.session_token:
            client_kwargs["aws_session_token"] = config.session_token

    return boto3.client("s3", **client_kwargs)


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
