from enum import Enum
from typing import Any, Literal
from urllib.parse import quote

import boto3
from ska_ser_skuid import EntityType, ShortSkuid
from botocore.client import BaseClient, Config

from ska_oso_services.settings import PRESIGNED_URL_EXPIRY_TIME, S3Config, get_settings

ProposalID = ShortSkuid[Literal[EntityType.PRP]]

class S3Method(str, Enum):
    GET = "get_object"
    PUT = "put_object"
    DELETE = "delete_object"


def get_s3_object_key(prsl_id: ProposalID, filename: str) -> str:
    """Build a proposal-scoped S3 key for PHT proposal documents."""
    return f"{str(prsl_id).strip('/')}/{filename.lstrip('/')}"


def get_aws_client(config: S3Config | None = None) -> BaseClient:
    config = config or get_settings().s3
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
    extra_params: dict[str, str] | None = None,
) -> str:
    config = config or get_settings().s3
    params = {"Bucket": config.bucket, "Key": key}
    if extra_params:
        params.update(extra_params)
    return client.generate_presigned_url(
        ClientMethod=method.value,
        Params=params,
        ExpiresIn=config.expiry,
    )


def build_content_disposition(filename: str) -> str:
    """Build a safe RFC5987 content-disposition value for downloads."""
    cleaned = filename.replace("\r", "").replace("\n", "").strip()
    fallback = cleaned.encode("ascii", "ignore").decode("ascii").replace('"', "")
    if not fallback:
        fallback = "download.pdf"
    encoded = quote(cleaned, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def create_presigned_url_upload_pdf(
    key: str,
    client: BaseClient,
    expiry: int = PRESIGNED_URL_EXPIRY_TIME,
    content_disposition: str | None = None,
) -> str:
    """
    Generate a presigned S3 upload URL for the given filename.
    """
    config = get_settings().s3.model_copy(update={"expiry": expiry})
    extra_params = {"ContentDisposition": content_disposition} if content_disposition else None
    return generate_presigned_url(key, S3Method.PUT, client, config, extra_params=extra_params)


def create_presigned_url_download_pdf(
    key: str,
    client: BaseClient,
    expiry: int = PRESIGNED_URL_EXPIRY_TIME,
    response_content_disposition: str | None = None,
) -> str:
    """
    Generate a presigned S3 download URL for the given filename.
    """
    config = get_settings().s3.model_copy(update={"expiry": expiry})
    extra_params = (
        {"ResponseContentDisposition": response_content_disposition}
        if response_content_disposition
        else None
    )
    return generate_presigned_url(key, S3Method.GET, client, config, extra_params=extra_params)


def create_presigned_url_delete_pdf(
    key: str, client: BaseClient, expiry: int = PRESIGNED_URL_EXPIRY_TIME
) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.
    """
    config = get_settings().s3.model_copy(update={"expiry": expiry})
    return generate_presigned_url(key, S3Method.DELETE, client, config)
