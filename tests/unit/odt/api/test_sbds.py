"""
Unit tests for ska_oso_services.api
"""

from http import HTTPStatus
from unittest import mock

import pytest
from ska_db_oda.repository.domain import ODANotFound

from ska_oso_services.common.model import ValidationResponse
from tests.unit.conftest import ODT_BASE_API_URL
from tests.unit.util import (
    SBDEFINITION_WITHOUT_ID_JSON,
    VALID_MID_SBDEFINITION_JSON,
    TestDataFactory,
    assert_json_is_equal,
)

SBDS_API_URL = f"{ODT_BASE_API_URL}/sbds"


class TestSBDefinitionAPI:
    def test_sbds_create(self, client_with_uow_mock):
        """
        Confirm that a call to /sbd/create
         - returns an empty SBD with an SBD ID and valid metadata
         - does not interact with ODA.
        """
        client, uow_mock = client_with_uow_mock
        response = client.get(f"{SBDS_API_URL}/create")

        assert response.status_code == HTTPStatus.OK
        result = response.json()

        # assert defaults are all set correctly
        assert result["interface"] == "https://schema.skao.int/ska-oso-pdm-sbd/0.1"

        # No ODA interactions expected for a create operation
        uow_mock.add.assert_not_called()
        uow_mock.get.assert_not_called()

    def test_sbds_get_existing_sbd(self, client_with_uow_mock):
        """
        Check the sbds_get method returns the expected SBD and status code
        """
        client, uow_mock = client_with_uow_mock
        test_sbd = TestDataFactory.sbdefinition()
        uow_mock.sbds.get.return_value = test_sbd

        response = client.get(f"{SBDS_API_URL}/sbd-1234")

        assert_json_is_equal(response.text, test_sbd.model_dump_json())
        assert response.status_code == HTTPStatus.OK

    def test_sbds_get_not_found_sbd(self, client_with_uow_mock):
        """
        Check the sbds_get method returns the Not Found error when identifier not in ODA
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.get.side_effect = ODANotFound(identifier="sbd-1234")

        response = client.get(f"{SBDS_API_URL}/sbd-1234")

        assert response.json()["detail"] == "The requested identifier sbd-1234 could not be found."
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_sbds_get_error(self, client_with_uow_mock):
        """
        Check the sbds_get method returns a formatted error
        when ODA responds with an error
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.get.side_effect = ValueError("test", "error")

        with pytest.raises(ValueError):
            response = client.get(f"{SBDS_API_URL}/sbd-1234")
            detail = response.json()["detail"]

            assert detail["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert detail["title"] == "Internal Server Error"
            assert detail["detail"] == "ValueError('test', 'error')"
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_validate_valid_sbd(self, mock_validate, client):
        """
        Check the sbds_validate handles a valid return value from the
        validation layer and creates the correct response
        """
        mock_validate.return_value = {}
        response = client.post(
            f"{SBDS_API_URL}/validate",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.json() == {"valid": True, "messages": {}}
        assert response.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_validate_invalid_sbd(self, mock_validate, client):
        """
        Check the sbds_validate handles a valid return value from the
        validation layer and creates the correct response
        """
        mock_validate.return_value = {"validation_error": "some validation error message"}

        response = client.post(
            f"{SBDS_API_URL}/validate",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK
        expected = ValidationResponse(
            valid=False, messages={"validation_error": "some validation error message"}
        )
        assert response.json() == expected.model_dump(mode="json")

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_success(self, mock_validate, client_with_uow_mock):
        """
        Check the sbds_post method returns the expected response
        """
        mock_validate.return_value = {}
        client, uow_mock = client_with_uow_mock
        test_sbd = TestDataFactory.sbdefinition()
        uow_mock.sbds.add.return_value = test_sbd
        uow_mock.sbds.get.return_value = test_sbd

        response = client.post(
            f"{SBDS_API_URL}",
            data=SBDEFINITION_WITHOUT_ID_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert_json_is_equal(response.text, test_sbd.model_dump_json())

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_given_sbd_id_raises_error(self, mock_validate, client):
        """
        Check the sbds_post method returns a validation error if the user
        gives an sbd_id in the body, as we don't want to just silently overwrite this
        """
        mock_validate.return_value = {}

        response = client.post(
            f"{SBDS_API_URL}",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "detail": (
                "sbd_id given in the body of the POST request. Identifier generation"
                " for new entities is the responsibility of the ODA, which will fetch"
                " them from SKUID, so they should not be given in this request."
            )
        }

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_value_error(self, mock_validate, client):
        """
        Check the sbds_post method returns the validation error in a response
        """
        mock_validate.return_value = {"validation_errors": "some validation error"}
        response = client.post(
            f"{SBDS_API_URL}",
            data=SBDEFINITION_WITHOUT_ID_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.json() == {
            "detail": {
                "valid": False,
                "messages": {"validation_errors": "some validation error"},
            }
        }
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_oda_error(self, mock_validate, client_with_uow_mock):
        """
        Check the sbds_post method returns the expected error response
        from an error in the ODA
        """
        mock_validate.return_value = {}
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.add.side_effect = IOError("test error")

        with pytest.raises(IOError):
            response = client.post(
                f"{SBDS_API_URL}",
                data=SBDEFINITION_WITHOUT_ID_JSON,
                headers={"Content-type": "application/json"},
            )

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert response.json() == {"detail": "OSError('test error')"}

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_success(self, mock_validate, client_with_uow_mock):
        """
        Check the sbds_put method returns the expected response
        """
        mock_validate.return_value = {}
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.__contains__.return_value = True
        test_sbd = TestDataFactory.sbdefinition()
        uow_mock.sbds.add.return_value = test_sbd
        uow_mock.sbds.get.return_value = test_sbd

        response = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert_json_is_equal(response.text, test_sbd.model_dump_json())

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_wrong_identifier(self, mock_validate, client):
        """
        Check the sbds_put method returns the expected error response
        when the identifier in the path doesn't match the sbd_id in the SBDefinition
        """
        mock_validate.return_value = {}
        response = client.put(
            f"{SBDS_API_URL}/00000",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert response.json() == {
            "detail": (
                "There is a mismatch between the SBD " "ID for the endpoint and the JSON payload"
            )
        }

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_value_error(self, mock_validate, client):
        """
        Check the sbds_put method returns the validation error in a response
        """
        mock_validate.return_value = {"validation_errors": "some validation error"}

        response = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "detail": {
                "valid": False,
                "messages": {"validation_errors": "some validation error"},
            }
        }

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_not_found(self, mock_validate, client_with_uow_mock):
        """
        Check the sbds_put method returns the expected error response
        when the identifier is not found in the ODA.
        """
        mock_validate.return_value = {}
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.get.side_effect = ODANotFound(identifier="sbd-mvp01-20200325-00001")

        response = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert (
            response.json()["detail"]
            == "The requested identifier sbd-mvp01-20200325-00001 could not be found."
        )

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_oda_error(self, mock_validate, client_with_uow_mock):
        """
        Check the sbds_put method returns the expected error response
        from an error in the ODA
        """
        mock_validate.return_value = {}
        client, uow_mock = client_with_uow_mock
        uow_mock.sbds.__contains__.return_value = True
        uow_mock.sbds.add.side_effect = IOError("test error")

        with pytest.raises(IOError):
            response = client.put(
                f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
                data=VALID_MID_SBDEFINITION_JSON,
                headers={"Content-type": "application/json"},
            )

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert response.json() == {"detail": "OSError('test error')"}
