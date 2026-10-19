from types import SimpleNamespace
from unittest import mock

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.api.prsls import ProposalDocument
from tests.conftest import PHT_BASE_API_URL

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/prsls"
PRSL_ID = "prp-test123"
SCIENCE_FILENAME = "science-upload.pdf"
TECHNICAL_FILENAME = "technical-upload.pdf"
SV_DESCRIPTION_FILENAME = "sv-description-upload.pdf"
PANEL_ID = "pnl-t1"


class TestSignedUrlDelete:
    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch("ska_oso_services.pht.api.prsls.create_presigned_url_delete_pdf", autospec=True)
    def test_create_delete_url_success(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/delete-url"
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/delete/{ProposalDocument.TECHNICAL}"
        )

        assert response.status_code == 200
        mock_create_url.assert_called_once()
        assert mock_create_url.call_args.kwargs["key"] == f"{PRSL_ID}/technical"

        assert response.text.strip('"') == "https://s3/delete-url"

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError())
    def test_create_delete_url_boto_core_error(self, mock_get_client, client):
        """
        Test that a BotoCoreError is handled correctly
        """
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/delete/{ProposalDocument.SV_DESCRIPTION}"
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
    def test_create_delete_url_client_error(self, mock_create_url, mock_get_client, client):
        """
        Test that a ClientError is handled correctly
        """
        mock_get_client.return_value = mock.MagicMock()

        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/delete/{ProposalDocument.SCIENCE}"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate delete URL" in response.text


class TestSignedUrlUpload:
    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch("ska_oso_services.pht.api.prsls.create_presigned_url_upload_pdf", autospec=True)
    def test_create_upload_url_success(self, mock_create_url, mock_get_client, client):
        """
        Test that a presigned URL for uploading a file is created successfully
        """
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/upload-url"
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/upload/{ProposalDocument.SCIENCE}?filename={SCIENCE_FILENAME}"
        )

        assert response.status_code == 200
        mock_create_url.assert_called_once()
        assert mock_create_url.call_args.kwargs["key"] == f"{PRSL_ID}/science"
        assert response.text.strip('"') == "https://s3/upload-url"

    def test_create_upload_url_invalid_filename(self, client):
        """
        Test that an invalid filename returns a 422 error
        """
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/upload/{ProposalDocument.TECHNICAL}?filename=bad%5Cname.pdf"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "filename" in response.text

    def test_create_upload_url_invalid_slot(self, client):
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/upload/other?filename={SCIENCE_FILENAME}"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "document_type" in response.text

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError())
    def test_create_upload_url_boto_core_error(self, mock_get_client, client):
        """
        Test that a BotoCoreError is handled correctly
        """
        # Mock the S3 client to raise a BotoCoreError
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/upload/{ProposalDocument.SV_DESCRIPTION}?filename={SV_DESCRIPTION_FILENAME}"
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
    def test_create_upload_url_client_error(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/upload/{ProposalDocument.TECHNICAL}?filename={TECHNICAL_FILENAME}"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate upload URL" in response.text


class TestSignedUrlDownload:
    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_download_pdf",
        autospec=True,
    )
    def test_create_download_url_success(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        mock_create_url.return_value = "https://s3/download-url"
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/download/{ProposalDocument.SV_DESCRIPTION}"
        )

        assert response.status_code == 200
        mock_create_url.assert_called_once()
        assert mock_create_url.call_args.kwargs["key"] == f"{PRSL_ID}/sv-description"
        assert response.text.strip('"') == "https://s3/download-url"

    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", side_effect=BotoCoreError())
    def test_create_download_url_boto_core_error(self, mock_get_client, client):
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/download/{ProposalDocument.TECHNICAL}"
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
    def test_create_download_url_client_error(self, mock_create_url, mock_get_client, client):
        mock_get_client.return_value = mock.MagicMock()
        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/download/{ProposalDocument.SCIENCE}"
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Failed to generate download URL" in response.text

    @pytest.mark.parametrize(
        "panel_proposals, expected_status",
        [([PRSL_ID], status.HTTP_200_OK), (["prp-other"], status.HTTP_403_FORBIDDEN)],
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow")
    @mock.patch("ska_oso_services.pht.api.prsls.get_aws_client", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.prsls.create_presigned_url_download_pdf",
        autospec=True,
    )
    def test_panel_reviewer_can_download_only_assigned_proposals(
        self, mock_create_url, mock_get_client, mock_uow, client, panel_proposals, expected_status
    ):
        mock_create_url.return_value = "https://s3/download-url"
        uow = mock_uow.return_value.__enter__.return_value
        uow.panels.get.return_value = SimpleNamespace(
            proposals=[SimpleNamespace(prsl_id=prsl_id) for prsl_id in panel_proposals]
        )
        # A panel member, but not a member of the proposal
        token = mint_test_token(
            audience="test:pht",
            roles=[Role.ANY],
            scopes=[Scope.PHT_READ],
            groups=[f"app:pht:{PANEL_ID}"],
        )

        response = client.post(
            f"{PROPOSAL_API_URL}/{PRSL_ID}/s3/download/{ProposalDocument.SCIENCE}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == expected_status, response.text
        uow.panels.get.assert_called_once_with(PANEL_ID)
