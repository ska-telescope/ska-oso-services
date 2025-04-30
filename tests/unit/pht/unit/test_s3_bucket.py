import unittest

import boto3
from moto import mock_aws

from ska_oso_pht_services.utils.s3_bucket import (
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
)

PRESIGNED_URL_EXPIRY_TIME = 60


@mock_aws
class TestS3Bucket(unittest.TestCase):
    def setUp(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="mybucket")

    def test_create_presigned_url_download_pdf(self):
        s3 = boto3.client("s3")

        result = create_presigned_url_download_pdf(
            "example.pdf", s3, PRESIGNED_URL_EXPIRY_TIME, "mybucket"
        )

        from_client = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": "mybucket",
                "Key": "example.pdf",
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY_TIME,
        )
        assert result == from_client

    def test_create_presigned_url_upload_pdf(self):
        s3 = boto3.client("s3")

        result = create_presigned_url_upload_pdf(
            "example.pdf", s3, PRESIGNED_URL_EXPIRY_TIME, "mybucket"
        )

        from_client = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": "mybucket",
                "Key": "example.pdf",
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY_TIME,
        )
        assert result == from_client

    def test_create_presigned_url_delete_pdf(self):
        s3 = boto3.client("s3")

        result = create_presigned_url_delete_pdf(
            "example.pdf", s3, PRESIGNED_URL_EXPIRY_TIME, "mybucket"
        )

        from_client = s3.generate_presigned_url(
            ClientMethod="delete_object",
            Params={
                "Bucket": "mybucket",
                "Key": "example.pdf",
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY_TIME,
        )
        assert result == from_client
