"""
Unit tests for ska_oso_pht_services.api
"""

import json
from http import HTTPStatus
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import VALID_NEW_PROPOSAL, TestDataFactory, load_string_from_file

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/proposal"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


class TestProposalAPI:
    @mock.patch("ska_oso_services.pht.api.ppt.oda.uow", autospec=True)
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

    @mock.patch("ska_oso_services.pht.api.ppt.oda.uow", autospec=True)
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
