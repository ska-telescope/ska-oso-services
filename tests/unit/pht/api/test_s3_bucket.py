from unittest import mock
from urllib.parse import quote

import pytest
from aiosmtplib.errors import SMTPException
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from fastapi.testclient import TestClient

from ska_oso_services.pht.utils.s3_bucket import (
    PRESIGNED_URL_EXPIRY_TIME,
    S3Config,
    S3Method,
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
    generate_presigned_url,
    get_aws_client,
)
from tests.unit.conftest import PHT_BASE_API_URL

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/prsls"


class TestSignedUrlDelete:

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_delete_pdf", autospec=True
    )
    def test_create_delete_url_success(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/delete-url"
        name = "delete-me"
        filename = f"{name}.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/delete/{filename}")

        assert response.status_code == 200

        assert response.text.strip('"') == "https://s3/delete-url"

    def test_create_delete_url_invalid_filename(self, client):
        filename = "bad\\name.pdf"  # invalid, but routed OK
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/delete/{filename}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid filename" in response.text

    @mock.patch(
        "ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError()
    )
    def test_create_delete_url_boto_core_error(self, mock_get_client, client):
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/delete/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Could not initialize S3 client" in response.text

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_delete_pdf",
        side_effect=ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "delete_object"
        ),
    )
    def test_create_delete_url_client_error(
        self, mock_create_url, mock_get_client, client
    ):
        mock_get_client.return_value = mock.MagicMock()

        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/delete/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate delete URL" in response.text


class TestSignedUrlUpload:

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_upload_pdf", autospec=True
    )
    def test_create_upload_url_success(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/upload-url"
        filename = "upload-me.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/upload/{filename}")

        assert response.status_code == 200
        assert response.text.strip('"') == "https://s3/upload-url"

    def test_create_upload_url_invalid_filename(self, client):
        filename = "bad\\upload.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/upload/{filename}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid filename" in response.text

    @mock.patch(
        "ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError()
    )
    def test_create_upload_url_boto_core_error(self, mock_get_client, client):
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/upload/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Could not initialize S3 client" in response.text

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_upload_pdf",
        side_effect=ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "put_object"
        ),
    )
    def test_create_upload_url_client_error(
        self, mock_create_url, mock_get_client, client
    ):
        mock_get_client.return_value = mock.MagicMock()
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/upload/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate upload URL" in response.text


class TestSignedUrlDownload:

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_download_pdf", autospec=True
    )
    def test_create_download_url_success(
        self, mock_create_url, mock_get_client, client
    ):
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/download-url"
        filename = "download-me.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/download/{filename}")

        assert response.status_code == 200
        assert response.text.strip('"') == "https://s3/download-url"

    def test_create_download_url_invalid_filename(self, client):
        filename = "bad\\download.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/download/{filename}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid filename" in response.text

    @mock.patch(
        "ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError()
    )
    def test_create_download_url_boto_core_error(self, mock_get_client, client):
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/download/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Could not initialize S3 client" in response.text

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_download_pdf",
        side_effect=ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "get_object"
        ),
    )
    def test_create_download_url_client_error(
        self, mock_create_url, mock_get_client, client
    ):
        mock_get_client.return_value = mock.MagicMock()
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/download/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate download URL" in response.text


class TestS3BucketUtils:

    def test_get_aws_client_returns_boto3_client(self):
        client = get_aws_client()
        assert client.meta.service_model.service_name == "s3"

    @mock.patch("boto3.client")
    def test_get_aws_client_invokes_boto3(self, mock_boto_client):
        get_aws_client()
        mock_boto_client.assert_called_once()

    def test_generate_presigned_url_calls_client(self):
        fake_client = mock.Mock()
        config = S3Config(bucket="test-bucket", expiry=120)
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
