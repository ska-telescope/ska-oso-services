"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus
from unittest import mock

from aiosmtplib.errors import SMTPConnectError, SMTPException, SMTPRecipientsRefused
from fastapi import status

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import (
    PAYLOAD_BAD_TO,
    PAYLOAD_CONNECT_FAIL,
    PAYLOAD_GENERIC_FAIL,
    PAYLOAD_SUCCESS,
    VALID_NEW_PROPOSAL,
    TestDataFactory,
    assert_json_is_equal,
)

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/prsls"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


class TestProposalAPI:
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_create_proposal(self, mock_oda, client):
        """
        Check the proposal_create method returns the expected prsl_id and status code.
        """

        proposal_obj = TestDataFactory.proposal()

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.return_value = proposal_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=VALID_NEW_PROPOSAL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == proposal_obj.prsl_id

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_create_proposal_value_error_raises_bad_request(self, mock_oda, client):
        """
        Simulate ValueError in proposal creation and ensure it raises BadRequestError.
        """

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.side_effect = ValueError("mock-failure")

        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=VALID_NEW_PROPOSAL,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a proposal" in data["detail"]

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_not_found(self, mock_oda, client):
        """
        Ensure KeyError during get() raises NotFoundError (404).
        """
        proposal_id = "prsl-missing-9999"

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = KeyError(proposal_id)
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Could not find proposal" in response.json()["detail"]

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_success(self, mock_oda, client):
        """
        Ensure valid proposal ID returns the Proposal object.
        """
        proposal = TestDataFactory.proposal()
        proposal_id = proposal.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["prsl_id"] == proposal_id
        assert data["info"]["title"] == proposal.info.title

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_list_success(self, mock_oda, client):
        """
        Check if the get_proposals_for_user returns proposals correctly.
        """
        proposal_objs = [TestDataFactory.proposal(), TestDataFactory.proposal()]
        uow_mock = mock.MagicMock()
        uow_mock.prsls.query.return_value = proposal_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "DefaultUser"
        response = client.get(f"{PROPOSAL_API_URL}/list/{user_id}")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == len(proposal_objs)

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_list_none(self, mock_oda, client):
        """
        Should return empty list if no proposals are found.
        """
        uow_mock = mock.MagicMock()
        uow_mock.prsls.query.return_value = None
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "user123"
        response = client.get(f"{PROPOSAL_API_URL}/list/{user_id}")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_success(self, mock_uow, client):
        """
        Check the prsls_put method returns the expected response
        """
        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id
        uow_mock.prsls.add.return_value = proposal_obj
        uow_mock.prsls.get.return_value = proposal_obj
        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, proposal_obj.model_dump_json())

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_not_found(self, mock_uow, client):
        """
        Should return 404 if proposal doesn't exist.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_id_mismatch(self, mock_uow, client):
        """
        Should raise 422 when ID in path != payload.
        """
        proposal_obj = TestDataFactory.proposal()
        path_id = "diff-id"

        response = client.put(
            f"{PROPOSAL_API_URL}/{path_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in response.json()["detail"].lower()

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_validation_error(self, mock_oda, client):
        """
        Should return 400 if .add() raises ValueError.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal_obj
        uow_mock.prsls.add.side_effect = ValueError("Invalid proposal content")
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "validation error" in response.json()["detail"].lower()


class TestProposalEmailAPI:
    @mock.patch("ska_oso_services.pht.api.prsls.send_email_async", autospec=True)
    def test_send_email_success(self, mock_send, client):
        """
        Check that a successful email send returns status 200 and success message.
        """
        mock_send.return_value = True

        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_SUCCESS,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Email sent successfully"}
        mock_send.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.utils.email_helper.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_connection_failure(self, mock_smtp_send, client):
        """
        Check that a SMTPConnectError returns status 503.
        """
        mock_smtp_send.side_effect = SMTPConnectError(b"Connection failed")
        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_CONNECT_FAIL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "SMTP connection failed" in response.text

    @mock.patch(
        "ska_oso_services.pht.utils.email_helper.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_recipients_refused(self, mock_smtp_send, client):
        """
        Check that SMTPRecipientsRefused returns status 400.
        """
        mock_smtp_send.side_effect = SMTPRecipientsRefused({})
        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_BAD_TO,
            headers={"Content-type": "application/json"},
        )

        assert "Unable to send email for this recipient." in response.text

    @mock.patch(
        "ska_oso_services.pht.utils.email_helper.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_generic_smtp_exception(self, mock_smtp_send, client):
        """
        Check that generic SMTPException returns 502.
        """
        mock_smtp_send.side_effect = SMTPException("Some SMTP error")

        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_GENERIC_FAIL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "SMTP send failed" in response.text
