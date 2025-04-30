"""
Unit tests for ska_oso_pht_services.api
"""

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

# from ska_oso_pdm.generated.models.proposal import Proposal
from ska_oso_pdm import Proposal
from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC

from .util import (
    VALID_PROPOSAL_DATA_JSON,
    VALID_PROPOSAL_GET_LIST_RESULT_JSON,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_NO_TARGET_IN_RESULT,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_OBS_SET_NO_TARGET,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_PASSING,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_RESULT_NO_OBS,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_NO_TARGET_IN_RESULT,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_OBS_SET_NO_TARGET,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_PASSING,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_RESULT_NO_OBS,
    assert_json_is_equal,
    assert_json_is_equal_unsorted,
)


@patch("ska_oso_pht_services.api.oda.uow", autospec=True)
def test_proposal_create(mock_oda, client):
    """
    Check the proposal_create method returns the expected prsl_id and status code
    """

    uow_mock = MagicMock()
    uow_mock.prsls.add.return_value = OPENAPI_CODEC.loads(
        Proposal, VALID_PROPOSAL_DATA_JSON
    )
    mock_oda.return_value.__enter__.return_value = uow_mock

    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.text == "prp-ska01-202204-01"
    assert response.status_code == HTTPStatus.OK


@patch("ska_oso_pht_services.api.oda.uow", autospec=True)
def test_proposal_get(mock_oda, client):
    uow_mock = MagicMock()
    uow_mock.prsls.get.return_value = Proposal.model_validate(
        json.loads(VALID_PROPOSAL_DATA_JSON)
    )
    mock_oda.return_value.__enter__.return_value = uow_mock

    response = client.get(
        "/ska-oso-pht-services/pht/api/v2/proposals/prp-ska01-202204-01",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal(response.text, VALID_PROPOSAL_DATA_JSON)


@patch("ska_oso_pht_services.api.oda.uow", autospec=True)
def test_proposal_get_list(mock_oda, client):
    list_result = json.loads(VALID_PROPOSAL_GET_LIST_RESULT_JSON)

    return_value = []
    for x in list_result:
        return_value.append(OPENAPI_CODEC.loads(Proposal, json.dumps(x)))

    uow_mock = MagicMock()
    uow_mock.prsls.query.return_value = return_value

    mock_oda.return_value.__enter__.return_value = uow_mock

    response = client.get("/ska-oso-pht-services/pht/api/v2/proposals/list/DefaultUser")

    assert response.status_code == HTTPStatus.OK
    assert len(json.loads(response.text)) == len(list_result)


@patch("ska_oso_pht_services.api.oda.uow", autospec=True)
def test_proposal_edit(mock_oda, client):
    uow_mock = MagicMock()
    uow_mock.prsls.get.return_value = OPENAPI_CODEC.loads(
        Proposal, VALID_PROPOSAL_DATA_JSON
    )

    mock_oda.return_value.__enter__.return_value = uow_mock

    response = client.put(
        "/ska-oso-pht-services/pht/api/v2/proposals/prp-ska01-202204-01",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal(response.text, VALID_PROPOSAL_DATA_JSON)


def test_validate_proposal_no_target_in_result(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_NO_TARGET_IN_RESULT,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_NO_TARGET_IN_RESULT
    )


def test_validate_proposal_obs_set_no_target(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_OBS_SET_NO_TARGET,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_OBS_SET_NO_TARGET
    )


def test_validate_proposal_result_no_obs(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_RESULT_NO_OBS,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_RESULT_NO_OBS
    )


def test_validate_proposal_result_sample_proposal(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON
    )


def test_validate_proposal_result_passing(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_PASSING,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_PASSING
    )


@pytest.mark.skip(
    reason="revisit test for validate endpoint after refactoring with new pdm data"
)
def test_validate_proposal_target_not_found(client):
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/proposals/validate",
        data=VALID_PROPOSAL_GET_VALIDATE_BODY_JSON_TARGET_NOT_FOUND,  # noqa
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        response.text, VALID_PROPOSAL_GET_VALIDATE_RESULT_JSON_TARGET_NOT_FOUND  # noqa
    )


class TestGetSignedUrl:
    test_case = "prsl-1234-science.pdf"

    def test_get_upload_signed_url(self, client):
        for data in self.test_case:
            self.get_upload_signed_url(client, *data)

    def test_get_download_signed_url(self, client):
        for data in self.test_case:
            self.get_download_signed_url(client, *data)

    def get_upload_signed_url(self, client, name):
        base_url = "/ska-oso-pht-services/pht/api/v2/upload/signedurl/"

        response = client.get(f"{base_url}{name}")
        assert response.status_code == HTTPStatus.OK

    def get_download_signed_url(self, client, name):
        base_url = "/ska-oso-pht-services/pht/api/v2/download/signedurl/"

        response = client.get(f"{base_url}{name}")
        assert response.status_code == HTTPStatus.OK


class TestGetCoordinates:
    test_cases = [
        (
            "M31",
            "test",
            {
                "equatorial": {
                    "ra": "00:42:44.330",
                    "dec": "+41:16:07.500",
                    "redshift": -0.0010006922855944561,
                    "velocity": -300.0,
                }
            },
        ),
        (
            "N10",
            "galactic",
            {
                "galactic": {
                    "lat": -78.5856,
                    "lon": 354.21,
                    "redshift": 0.022945539640067736,
                    "velocity": 6800.0,
                }
            },
        ),
        (
            "N10",
            "equatorial",
            {
                "equatorial": {
                    "dec": "-33:51:30.197",
                    "ra": "00:08:34.539",
                    "redshift": 0.022945539640067736,
                    "velocity": 6800.0,
                }
            },
        ),
        (
            "M1",
            "",
            {
                "equatorial": {
                    "dec": "",
                    "ra": "",
                    "redshift": None,
                    "velocity": None,
                }
            },
        ),
    ]

    def get_coordinates_generic(self, client, name, reference_frame, expected_response):
        base_url = "/ska-oso-pht-services/pht/api/v2/coordinates/"
        if not reference_frame:
            response = client.get(f"{base_url}{name}")
            assert response.status_code == HTTPStatus.NOT_FOUND
            return

        response = client.get(f"{base_url}{name}/{reference_frame}")
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.data.decode()) == expected_response

    def test_get_coordinates(self, client):
        for data in self.test_cases:
            self.get_coordinates_generic(client, *data)


def test_send_email_success(client, mocker):
    # Mock the smtplib.SMTP object to avoid actually sending emails during the test
    mock_smtp = mocker.patch("smtplib.SMTP")

    # Mock the response of sendmail method
    mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
    mock_smtp_instance.sendmail.return_value = {"message": "Email sent successfully!"}

    # Define the email data to be sent
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/send-email",
        json={"email": "recipient@example.com", "prsl_id": "test-prsl-id-123"},
    )

    # Assert that the response status code is 200 (success)
    assert response.status_code == HTTPStatus.OK
    assert b"Email sent successfully" in response.data


def test_send_email_failure(client, mocker):
    # Mock the smtplib.SMTP object to raise an exception
    mock_smtp = mocker.patch("smtplib.SMTP")
    mock_smtp.side_effect = Exception("SMTP connection error")

    # Define the email data to be sent
    response = client.post(
        "/ska-oso-pht-services/pht/api/v2/send-email",
        json={"email": "recipient@example.com", "prsl_id": "test-prsl-id-123"},
    )

    # Assert that the response status code is 500 (internal server error)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert b"SMTP connection error" in response.data
