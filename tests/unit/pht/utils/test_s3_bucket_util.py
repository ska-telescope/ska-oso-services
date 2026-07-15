from unittest import mock

import pytest

import ska_oso_services.settings as settings_module
from ska_oso_services.pht.service.s3_bucket import (
    S3Config,
    S3Method,
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
    generate_presigned_url,
    get_aws_client,
)
from ska_oso_services.settings import get_settings


class TestS3BucketUtils:
    @pytest.fixture(autouse=True)
    def _mock_s3_settings(self):
        current = get_settings()
        with mock.patch.object(
            settings_module,
            "SETTINGS",
            get_settings().model_copy(
                update={
                    "s3": current.s3.model_copy(
                        update={"bucket": "test-bucket", "region": "eu-west-2"}
                    )
                },
            ),
        ):
            yield

    def test_get_aws_client_returns_boto3_client(self):
        client = get_aws_client()
        assert client.meta.service_model.service_name == "s3"

    @mock.patch("boto3.client")
    def test_get_aws_client_invokes_boto3(self, mock_boto_client):
        config = S3Config(
            access_key=None,
            secret_key=None,
            bucket="test-bucket",
            region="eu-west-2",
        )

        get_aws_client(config)

        mock_boto_client.assert_called_once_with(
            "s3",
            region_name="eu-west-2",
            config=mock.ANY,
        )

    @mock.patch("boto3.client")
    def test_get_aws_client_with_explicit_credentials(self, mock_boto_client):
        config = S3Config(
            access_key="test-access-key",
            secret_key="test-secret-key",
            session_token="test-session-token",
            bucket="test-bucket",
            region="eu-west-2",
        )

        get_aws_client(config)

        mock_boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_session_token="test-session-token",
            region_name="eu-west-2",
            config=mock.ANY,
        )

    def test_generate_presigned_url_calls_client(self):
        fake_client = mock.Mock()
        config = S3Config(bucket="test-bucket", region="eu-west-2", expiry=120)
        generate_presigned_url("file.pdf", S3Method.PUT, fake_client, config)
        fake_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="put_object",
            Params={"Bucket": "test-bucket", "Key": "file.pdf"},
            ExpiresIn=120,
        )

    def test_create_presigned_url_upload_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_upload_pdf("upload.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()

    def test_create_presigned_url_download_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_download_pdf("download.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()

    def test_create_presigned_url_delete_pdf_delegates(self):
        mock_client = mock.Mock()
        create_presigned_url_delete_pdf("delete.pdf", mock_client)
        mock_client.generate_presigned_url.assert_called_once()
