from enum import Enum
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient, Config
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PRESIGNED_URL_EXPIRY_TIME = 60


class S3Method(str, Enum):
    GET = "get_object"
    PUT = "put_object"
    DELETE = "delete_object"


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    access_key: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    secret_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    bucket: str = Field(alias="AWS_PHT_BUCKET_NAME")
    region: str = Field(alias="AWS_REGION")
    expiry: int = Field(default=PRESIGNED_URL_EXPIRY_TIME, alias="PRESIGNED_URL_EXPIRY_TIME")


@lru_cache
def get_s3_config() -> S3Config:
    return S3Config()


def get_aws_client(config: S3Config | None = None) -> BaseClient:
    config = config or get_s3_config()
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
    config: S3Config | None = None,
) -> str:
    config = config or get_s3_config()
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
    config = get_s3_config().model_copy(update={"expiry": expiry})
    return generate_presigned_url(key, S3Method.PUT, client, config)


def create_presigned_url_download_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 download URL for the given filename.
    """
    config = get_s3_config().model_copy(update={"expiry": expiry})
    return generate_presigned_url(key, S3Method.GET, client, config)


def create_presigned_url_delete_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.
    """
    config = get_s3_config().model_copy(update={"expiry": expiry})
    return generate_presigned_url(key, S3Method.DELETE, client, config)
