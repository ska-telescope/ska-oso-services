"""
Unit tests for ska_oso_services.api
"""
from dataclasses import asdict
from http import HTTPStatus
from importlib.metadata import version
from unittest import mock

from ska_oso_services.common.model import ValidationResponse
from tests.unit.util import (
    SBDEFINITION_WITHOUT_ID_JSON,
    VALID_MID_SBDEFINITION_JSON,
    TestDataFactory,
    assert_json_is_equal,
)

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
BASE_API_URL = f"/ska-oso-services/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"
SBDS_API_URL = f"{BASE_API_URL}/sbds"


class TestSBDefinitionAPI:
    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    def test_sbds_create(self, mock_oda, client):
        """
        Confirm that a call to /sbd/create
         - returns an empty SBD with an SBD ID and valid metadata
         - does not interact with ODA.
        """

        response = client.get(f"{SBDS_API_URL}/create")

        assert response.status_code == HTTPStatus.OK

        # assert defaults are all set correctly
        assert (
            response.json["interface"] == "https://schema.skao.int/ska-oso-pdm-sbd/0.1"
        )

        # No ODA interactions expected for a create operation
        mock_oda.add.assert_not_called()
        mock_oda.get.assert_not_called()

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    def test_sbds_get_existing_sbd(self, mock_oda, client):
        """
        Check the sbds_get method returns the expected SBD and status code
        """
        uow_mock = mock.MagicMock()
        uow_mock.sbds.get.return_value = TestDataFactory.sbdefinition()
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{SBDS_API_URL}/sbd-1234")

        assert_json_is_equal(result.text, VALID_MID_SBDEFINITION_JSON)
        assert result.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    def test_sbds_get_not_found_sbd(self, mock_oda, client):
        """
        Check the sbds_get method returns the Not Found error when identifier not in ODA
        """
        uow_mock = mock.MagicMock()
        uow_mock.sbds.get.side_effect = KeyError("not found")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{SBDS_API_URL}/sbd-1234")

        assert result.json == {
            "status": HTTPStatus.NOT_FOUND,
            "title": "Not Found",
            "detail": "Identifier sbd-1234 not found in repository",
            "traceback": None,
        }
        assert result.status_code == HTTPStatus.NOT_FOUND

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    def test_sbds_get_error(self, mock_oda, client):
        """
        Check the sbds_get method returns a formatted error
        when ODA responds with an error
        """
        uow_mock = mock.MagicMock()
        uow_mock.sbds.get.side_effect = Exception("test", "error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{SBDS_API_URL}/sbd-1234")

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "Exception('test', 'error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_validate_valid_sbd(self, mock_validate, client):
        """
        Check the sbds_validate handles a valid return value from the
        validation layer and creates the correct response
        """
        mock_validate.return_value = {}
        result = client.post(
            f"{SBDS_API_URL}/validate",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json == asdict(
            ValidationResponse(
                True,
                {},
            )
        )
        assert result.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_validate_invalid_sbd(self, mock_validate, client):
        """
        Check the sbds_validate handles a valid return value from the
        validation layer and creates the correct response
        """
        mock_validate.return_value = {
            "validation_error": "some validation error message"
        }

        result = client.post(
            f"{SBDS_API_URL}/validate",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json == asdict(
            ValidationResponse(
                False, {"validation_error": "some validation error message"}
            )
        )
        assert result.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_success(self, mock_validate, mock_oda, client):
        """
        Check the sbds_post method returns the expected response
        """
        mock_validate.return_value = {}
        uow_mock = mock.MagicMock()
        uow_mock.sbds.add.return_value = TestDataFactory.sbdefinition()
        uow_mock.sbds.get.return_value = TestDataFactory.sbdefinition()
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{SBDS_API_URL}",
            data=SBDEFINITION_WITHOUT_ID_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, VALID_MID_SBDEFINITION_JSON)

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_given_sbd_id_raises_error(self, mock_validate, client):
        """
        Check the sbds_post method returns a validation error if the user
        gives an sbd_id in the body, as we don't want to just silently overwrite this
        """
        mock_validate.return_value = {}

        result = client.post(
            f"{SBDS_API_URL}",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert result.json == {
            "status": HTTPStatus.BAD_REQUEST,
            "title": "Validation Failed",
            "detail": (
                "sbd_id given in the body of the POST request. Identifier generation"
                " for new entities is the responsibility of the ODA, which will fetch"
                " them from SKUID, so they should not be given in this request."
            ),
            "traceback": None,
        }

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_value_error(self, mock_validate, client):
        """
        Check the sbds_post method returns the validation error in a response
        """
        mock_validate.return_value = {"validation_errors": "some validation error"}

        result = client.post(
            f"{SBDS_API_URL}",
            data=SBDEFINITION_WITHOUT_ID_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json == {
            "valid": False,
            "messages": {"validation_errors": "some validation error"},
        }
        assert result.status_code == HTTPStatus.BAD_REQUEST

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_post_oda_error(self, mock_validate, mock_oda, client):
        """
        Check the sbds_post method returns the expected error response
        from an error in the ODA
        """
        mock_validate.return_value = {}
        uow_mock = mock.MagicMock()
        uow_mock.sbds.add.side_effect = IOError("test error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{SBDS_API_URL}",
            data=SBDEFINITION_WITHOUT_ID_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "OSError('test error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_success(self, mock_validate, mock_oda, client):
        """
        Check the sbds_put method returns the expected response
        """
        mock_validate.return_value = {}
        uow_mock = mock.MagicMock()
        uow_mock.sbds.__contains__.return_value = True
        uow_mock.sbds.add.return_value = TestDataFactory.sbdefinition()
        uow_mock.sbds.get.return_value = TestDataFactory.sbdefinition()
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert_json_is_equal(result.text, VALID_MID_SBDEFINITION_JSON)
        assert result.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_wrong_identifier(self, mock_validate, client):
        """
        Check the sbds_put method returns the expected error response
        when the identifier in the path doesn't match the sbd_id in the SBDefinition
        """
        mock_validate.return_value = {}

        result = client.put(
            f"{SBDS_API_URL}/00000",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json == {
            "status": HTTPStatus.UNPROCESSABLE_ENTITY,
            "title": "Unprocessable Entity, mismatched SBD IDs",
            "detail": (
                "There is a mismatch between the SBD "
                "ID for the endpoint and the JSON payload"
            ),
            "traceback": None,
        }
        assert result.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_value_error(self, mock_validate, client):
        """
        Check the sbds_put method returns the validation error in a response
        """
        mock_validate.return_value = {"validation_errors": "some validation error"}

        result = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json == {
            "valid": False,
            "messages": {"validation_errors": "some validation error"},
        }
        assert result.status_code == HTTPStatus.BAD_REQUEST

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_not_found(self, mock_validate, mock_oda, client):
        """
        Check the sbds_put method returns the expected error response
        when the identifier is not found in the ODA.
        """
        mock_validate.return_value = {}
        uow_mock = mock.MagicMock()
        uow_mock.sbds.__contains__.return_value = False
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.NOT_FOUND
        assert result.json["title"] == "Not Found"
        assert (
            result.json["detail"]
            == "Identifier sbd-mvp01-20200325-00001 not found in repository"
        )

    @mock.patch("ska_oso_services.odt.api.sbds.oda")
    @mock.patch("ska_oso_services.odt.api.sbds.validate_sbd")
    def test_sbds_put_oda_error(self, mock_validate, mock_oda, client):
        """
        Check the sbds_put method returns the expected error response
        from an error in the ODA
        """
        mock_validate.return_value = {}
        uow_mock = mock.MagicMock()
        uow_mock.sbds.__contains__.return_value = True
        uow_mock.sbds.add.side_effect = IOError("test error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.put(
            f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
            data=VALID_MID_SBDEFINITION_JSON,
            headers={"Content-type": "application/json"},
        )

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "OSError('test error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
