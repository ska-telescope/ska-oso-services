"""
Unit tests for ska_oso_services.api
"""

import json
from http import HTTPStatus
from importlib.metadata import version
from unittest import mock

from ska_oso_pdm.project import ObservingBlock

from tests.unit.util import TestDataFactory, assert_json_is_equal

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
BASE_API_URL = f"/ska-oso-services/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"
PRJS_API_URL = f"{BASE_API_URL}/prjs"


class TestProjectGet:
    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_get_existing_prj(self, mock_oda, client):
        """
        Check the prjs_get method returns the expected Project and status code
        """
        uow_mock = mock.MagicMock()
        project = TestDataFactory.project()
        uow_mock.prjs.get.return_value = project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{PRJS_API_URL}/prj-1234")

        assert_json_is_equal(result.text, project.model_dump_json())
        assert result.status_code == HTTPStatus.OK

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_get_not_found_prj(self, mock_oda, client):
        """
        Check the prjs_get method returns the Not Found error when identifier not in ODA
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.get.side_effect = KeyError("not found")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{PRJS_API_URL}/prj-1234")

        assert result.json == {
            "status": HTTPStatus.NOT_FOUND,
            "title": "Not Found",
            "detail": "Identifier prj-1234 not found in repository",
            "traceback": None,
        }
        assert result.status_code == HTTPStatus.NOT_FOUND

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_get_error(self, mock_oda, client):
        """
        Check the prjs_get method returns a formatted error
        when ODA responds with an error
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.get.side_effect = Exception("test", "error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.get(f"{PRJS_API_URL}/prj-1234")

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "Exception('test', 'error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectPost:
    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_success(self, mock_oda, client):
        """
        Check the prjs_post method returns the expected response
        """
        uow_mock = mock.MagicMock()
        created_project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = created_project
        uow_mock.prjs.get.return_value = created_project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}",
            data=TestDataFactory.project(prj_id=None).model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, created_project.model_dump_json())

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_with_minimum_body(self, mock_oda, client):
        """
        Check the prjs_post method returns an 'empty' project with a
        single observing block if a request body with only the valid fields is sent
        """
        uow_mock = mock.MagicMock()
        created_project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = created_project
        uow_mock.prjs.get.return_value = created_project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}",
            data=json.dumps({"telescope": "ska_mid"}),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, created_project.model_dump_json())
        # Check that the persisted value has an empty observing block
        args, _ = uow_mock.prjs.add.call_args
        assert len(args[0].obs_blocks) == 1

    def test_prjs_post_given_prj_id_raises_error(self, client):
        """
        Check the prjs_post method returns a validation error if the user
        gives a prj_id in the body, as we don't want to just silently overwrite this
        """

        result = client.post(
            f"{PRJS_API_URL}",
            data=TestDataFactory.project().model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert result.json == {
            "status": HTTPStatus.BAD_REQUEST,
            "title": "Validation Failed",
            "detail": (
                "prj_id given in the body of the POST request. Identifier generation"
                " for new entities is the responsibility of the ODA, which will fetch"
                " them from SKUID, so they should not be given in this request."
            ),
            "traceback": None,
        }

    # TODO validate sbd_ids exist?
    # TODO extract to service layer
    # @mock.patch("ska_oso_services.odt.api.prjs.validate_prj")
    # def test_sbds_post_value_error(self, mock_validate, client):
    #     """
    #     Check the sbds_post method returns the validation error in a response
    #     """
    #     mock_validate.return_value = {"validation_errors": ["some validation error"]}
    #
    #     result = client.post(
    #         f"{SBDS_API_URL}",
    #         data=SBDEFINITION_WITHOUT_ID_JSON,
    #         headers={"Content-type": "application/json"},
    #     )
    #
    #     assert result.json == {
    #         "status": HTTPStatus.BAD_REQUEST,
    #         "title": "Validation Failed",
    #         "detail": "SBD validation failed: 'some validation error'",
    #     }
    #     assert result.status_code == HTTPStatus.BAD_REQUEST

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_oda_error(self, mock_oda, client):
        """
        Check the prjs_post method returns the expected error response
        from an error in the ODA
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.add.side_effect = IOError("test error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}",
            data=TestDataFactory.project(prj_id=None).model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "OSError('test error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectPut:
    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_put_success(self, mock_oda, client):
        """
        Check the prjs_put method returns the expected response
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.__contains__.return_value = True
        project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = project
        uow_mock.prjs.get.return_value = project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.put(
            f"{PRJS_API_URL}/{project.prj_id}",
            data=project.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, project.model_dump_json())

    def test_prjs_put_wrong_identifier(self, client):
        """
        Check the prjs_put method returns the expected error response
        when the identifier in the path doesn't match the prj_id in the SBDefinition
        """
        result = client.put(
            f"{PRJS_API_URL}/00000",
            data=TestDataFactory.project().model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.json == {
            "status": HTTPStatus.UNPROCESSABLE_ENTITY,
            "title": "Unprocessable Entity, mismatched IDs",
            "detail": "There is a mismatch between the prj_id in the "
            "path for the endpoint and in the JSON payload",
            "traceback": None,
        }
        assert result.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # def test_sbds_put_value_error(self, mock_validate, client):
    #     """ TODO validation
    #     Check the sbds_put method returns the validation error in a response
    #     """
    #     mock_validate.return_value = {"validation_errors": ["some validation error"]}
    #
    #     result = client.put(
    #         f"{SBDS_API_URL}/sbd-mvp01-20200325-00001",
    #         data=VALID_MID_SBDEFINITION_JSON,
    #         headers={"Content-type": "application/json"},
    #     )
    #
    #     assert result.json == {
    #         "status": HTTPStatus.BAD_REQUEST,
    #         "title": "Validation Failed",
    #         "detail": "SBD validation failed: 'some validation error'",
    #     }
    #     assert result.status_code == HTTPStatus.BAD_REQUEST

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_put_not_found(self, mock_oda, client):
        """
        Check the prjs_put method returns the expected error response
        when the identifier is not found in the ODA.
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.__contains__.return_value = False
        mock_oda.uow.__enter__.return_value = uow_mock

        project = TestDataFactory.project(prj_id="prj-999")
        result = client.put(
            f"{PRJS_API_URL}/{project.prj_id}",
            data=project.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.NOT_FOUND
        assert result.json["title"] == "Not Found"
        assert result.json["detail"] == "Identifier prj-999 not found in repository"

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_put_oda_error(self, mock_oda, client):
        """
        Check the prjs_put method returns the expected error response
        from an error in the ODA
        """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.__contains__.return_value = True
        uow_mock.prjs.add.side_effect = IOError("test error")
        mock_oda.uow.__enter__.return_value = uow_mock

        project = TestDataFactory.project()
        result = client.put(
            f"{PRJS_API_URL}/{project.prj_id}",
            data=project.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "OSError('test error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectAddSBDefinition:
    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_sbd_prj_id_not_found(self, mock_oda, client):
        """ """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.get.side_effect = KeyError(
            "Identifier prj-999 not found in repository"
        )
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}/prj-999/ob-1/sbds",
        )

        assert result.status_code == HTTPStatus.NOT_FOUND
        assert result.json["title"] == "Not Found"
        assert result.json["detail"] == "Identifier prj-999 not found in repository"

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_sbd_obs_block_id_not_found(self, mock_oda, client):
        uow_mock = mock.MagicMock()
        project = TestDataFactory.project()
        project.obs_blocks = []
        uow_mock.prjs.get.return_value = project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/ob-1/sbds",
        )

        assert result.status_code == HTTPStatus.NOT_FOUND
        assert result.json["title"] == "Not Found"
        assert result.json["detail"] == "Observing Block 'ob-1' not found in Project"

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_sbd_oda_error(self, mock_oda, client):
        """ """
        uow_mock = mock.MagicMock()
        uow_mock.prjs.get.side_effect = IOError("test error")
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}/prj-123/ob-1/sbds",
        )

        assert result.json["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result.json["title"] == "Internal Server Error"
        assert result.json["detail"] == "OSError('test error')"
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @mock.patch("ska_oso_services.odt.api.prjs.oda")
    def test_prjs_post_sbd_success(self, mock_oda, client):
        uow_mock = mock.MagicMock()
        project = TestDataFactory.project()
        obs_block_id = "ob-1"
        project.obs_blocks = [ObservingBlock(obs_block_id=obs_block_id)]
        sbd = TestDataFactory.sbdefinition()
        uow_mock.prjs.get.return_value = project
        uow_mock.sbds.add.return_value = sbd
        uow_mock.prjs.add.return_value = project
        mock_oda.uow.__enter__.return_value = uow_mock

        result = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/{obs_block_id}/sbds",
        )

        assert result.status_code == HTTPStatus.OK

        expected_response = {
            "sbd": json.loads(sbd.model_dump_json()),
            "prj": json.loads(project.model_dump_json()),
        }
        assert expected_response == result.json

        args, _ = uow_mock.prjs.add.call_args
        assert sbd.sbd_id in args[0].obs_blocks[0].sbd_ids
