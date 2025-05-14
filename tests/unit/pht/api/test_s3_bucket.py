from unittest import mock
from urllib.parse import quote

import pytest
from aiosmtplib.errors import SMTPException
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from fastapi.testclient import TestClient

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

    @mock.patch(
        "ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError()
    )
    def test_create_delete_url_boto_core_error(self, mock_get_client, client):
        """
        Test that a BotoCoreError is handled correctly
        """
        response = client.post(
            f"{PROPOSAL_API_URL}/signed-url/delete/valid-filename.pdf"
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Could not initialize S3 client" in response.text

    @mock.patch("ska_oso_services.pht.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_delete_pdf",
        side_effect=ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "delete_object"
        ),
    )
    def test_create_delete_url_client_error(
        self, mock_create_url, mock_get_client, client
    ):
        """
        Test that a ClientError is handled correctly
        """
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
        """
        Test that a presigned URL for uploading a file is created successfully
        """
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/upload-url"
        filename = "upload-me.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/upload/{filename}")

        assert response.status_code == 200
        assert response.text.strip('"') == "https://s3/upload-url"

    def test_create_upload_url_invalid_filename(self, client):
        """
        Test that an invalid filename returns a 422 error
        """
        # Invalid filename with backslash
        # This is a common mistake when using Windows paths
        # and should be handled by the API
        filename = "bad\\upload.pdf"
        response = client.post(f"{PROPOSAL_API_URL}/signed-url/upload/{filename}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid filename" in response.text

    @mock.patch(
        "ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError()
    )
    def test_create_upload_url_boto_core_error(self, mock_get_client, client):
        """
        Test that a BotoCoreError is handled correctly
        """
        # Mock the S3 client to raise a BotoCoreError
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
        "ska_oso_services.pht.api.prsls.create_presigned_url_download_pdf",
        autospec=True,
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
