"""
Unit tests for ska_oso_services.api
"""

from http import HTTPStatus
from unittest import mock

import pytest
from pydantic import ValidationError
from ska_db_oda.repository.domain.errors import ODAIntegrityError, ODANotFound
from ska_oso_pdm.project import ObservingBlock

from tests.unit.conftest import ODT_BASE_API_URL
from tests.unit.util import TestDataFactory, assert_json_is_equal

PRJS_API_URL = f"{ODT_BASE_API_URL}/prjs"


class TestProjectGet:

    def test_prjs_get_existing_prj(self, client_with_uow_mock):
        """
        Check the prjs_get method returns the expected Project and status code
        """
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        uow_mock.prjs.get.return_value = project

        result = client.get(f"{PRJS_API_URL}/prj-1234")

        assert_json_is_equal(result.text, project.model_dump_json())
        assert result.status_code == HTTPStatus.OK

    def test_prjs_get_not_found_prj(self, client_with_uow_mock):
        """
        Check the prjs_get method returns the Not Found error when identifier not in ODA
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ODANotFound(identifier="prj-1234")

        result = client.get(f"{PRJS_API_URL}/prj-1234")
        assert result.json()["detail"] == "The requested identifier prj-1234 could not be found."
        assert result.status_code == HTTPStatus.NOT_FOUND

    def test_prjs_get_error(self, client_with_uow_mock):
        """
        Check the prjs_get method returns a formatted error
        when ODA responds with an error
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ValueError("Something bad!")

        # Middleware re-raises exceptions to make visible to tests and servers:
        # https://github.com/encode/starlette/blob/master/starlette/middleware/errors.py#L186
        with pytest.raises(ValueError):
            response = client.get(f"{PRJS_API_URL}/prj-1234")
            result = response.json()

            assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert result["title"] == "Internal Server Error"
            assert result["detail"] == "ValueError('Something bad!')"
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectStatus:

    def test_prjs_status_get_existing_prj(self, client_with_uow_mock):
        """
        Check the prjs_status_get method returns the expected Status and status code
        """
        client, uow_mock = client_with_uow_mock
        status = {"entity_id": "prj-1234", "status": "READY", "updated_by": "TestUser"}
        uow_mock.status.get_current_status.return_value = status

        result = client.get(f"{PRJS_API_URL}/prj-1234/status")

        assert result.status_code == HTTPStatus.OK
        assert result.json()["status"] == status["status"]

    def test_prjs_status_get_not_found_prj(self, client_with_uow_mock):
        """
        Check the prjs_status_get method returns the Not Found error when identifier not in ODA
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.status.get_current_status.side_effect = ODANotFound(identifier="prj-1234")

        result = client.get(f"{PRJS_API_URL}/prj-1234/status")

        assert result.json()["detail"] == "The requested identifier prj-1234 could not be found."
        assert result.status_code == HTTPStatus.NOT_FOUND


class TestProjectPost:

    def test_prjs_post_success(self, client_with_uow_mock):
        """
        Check the prjs_post method returns the expected response
        """
        client, uow_mock = client_with_uow_mock
        created_project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = created_project
        uow_mock.prjs.get.return_value = created_project

        result = client.post(
            f"{PRJS_API_URL}",
            data=TestDataFactory.project(prj_id=None).model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, created_project.model_dump_json())

    def test_prjs_post_with_minimum_body(self, client_with_uow_mock):
        """
        Check the prjs_post method returns an 'empty' project with a
        single observing block if a request body with only the valid fields is sent
        """
        client, uow_mock = client_with_uow_mock
        created_project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = created_project
        uow_mock.prjs.get.return_value = created_project

        result = client.post(f"{PRJS_API_URL}")

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
        assert result.json() == {
            "detail": (
                "prj_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of"
                " the ODA, which will fetch them from SKUID, so they"
                " should not be given in this request."
            )
        }

    # TODO validate sbd_ids exist?
    # TODO extract to service layer
    # @mock.patch("ska_oso_services.odt.api.prjs.validate_prj")
    # def test_sbds_post_value_error(self, mock_validate, client_with_uow_mock):
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

    def test_prjs_post_oda_error(self, client_with_uow_mock):
        """
        Check the prjs_post method returns the expected error response
        from an error in the ODA
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.add.side_effect = IOError("test error")

        # Middleware re-raises exceptions to make visible to tests and servers:
        # https://github.com/encode/starlette/blob/master/starlette/middleware/errors.py#L186
        with pytest.raises(IOError):
            response = client.post(
                f"{PRJS_API_URL}",
                data=TestDataFactory.project(prj_id=None).model_dump_json(),
                headers={"Content-type": "application/json"},
            )
            result = response.json()

            assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert result["title"] == "Internal Server Error"
            assert result["detail"] == "OSError('test error')"
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_prjs_oda_pydantic_error(self, client_with_uow_mock):
        """
        Check the prjs_post method returns the expected error response
        if pydantic fails to deserialise the ODA json
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.add.side_effect = ValidationError.from_exception_data(
            "Invalid data", line_errors=[]
        )

        response = client.post(
            f"{PRJS_API_URL}",
            data=TestDataFactory.project(prj_id=None).model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        result = response.json()

        assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert result["title"] == "Internal Validation Error"
        assert (
            result["detail"] == "Validation failed when reading from the ODA. "
            "Possible outdated data in the database:\n0 validation "
            "errors for Invalid data\n"
        )
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectPut:

    def test_prjs_put_success(self, client_with_uow_mock):
        """
        Check the prjs_put method returns the expected response
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.__contains__.return_value = True
        project = TestDataFactory.project()
        uow_mock.prjs.add.return_value = project
        uow_mock.prjs.get.return_value = project

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

        assert (
            result.json()["detail"]
            == "There is a mismatch between the prj_id in the path for the "
            "endpoint and in the JSON payload"
        )

        assert result.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # TODO currently no prj validation
    # @mock.patch("ska_oso_services.odt.api.prjs.validate_prj")
    # def test_sbds_put_value_error(self, mock_validate, client_with_uow_mock):
    #     """
    #     Check the sbds_put method returns the validation error in a response
    #     """
    #     mock_validate.return_value = {"validation_errors": "some validation error"}
    #     project = TestDataFactory.project()
    #
    #     response = client.put(
    #         f"{PRJS_API_URL}/{project.prj_id}",
    #         data=project.model_dump_json(),
    #         headers={"Content-type": "application/json"},
    #     )
    #
    #     assert response.status_code == HTTPStatus.BAD_REQUEST
    #     assert response.json() == {"detail": {
    #         "valid": False,
    #         "messages": {"validation_errors": "some validation error"},
    #     }}

    def test_prjs_put_not_found(self, client_with_uow_mock):
        """
        Check the prjs_put method returns the expected error response
        when the identifier is not found in the ODA.
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ODANotFound(identifier="prj-999")

        project = TestDataFactory.project(prj_id="prj-999")
        resp = client.put(
            f"{PRJS_API_URL}/{project.prj_id}",
            data=project.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "The requested identifier prj-999 could not be found."

    def test_prjs_put_oda_error(self, client_with_uow_mock):
        """
        Check the prjs_put method returns the expected error response
        from an error in the ODA
        """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.__contains__.return_value = True
        uow_mock.prjs.add.side_effect = IOError("test error")

        project = TestDataFactory.project()

        with pytest.raises(IOError):
            resp = client.put(
                f"{PRJS_API_URL}/{project.prj_id}",
                data=project.model_dump_json(),
                headers={"Content-type": "application/json"},
            )
            result = resp.json()["detail"]

            assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert result["title"] == "Internal Server Error"
            assert result["detail"] == "OSError('test error')"
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectAddSBDefinition:

    def test_prjs_post_sbd_prj_id_not_found(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ODANotFound(identifier="prj-999")

        resp = client.post(
            f"{PRJS_API_URL}/prj-999/ob-1/sbds",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "The requested identifier prj-999 could not be found."

    def test_prjs_post_sbd_obs_block_id_not_found(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        project.obs_blocks = []
        uow_mock.prjs.get.return_value = project

        resp = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/ob-1/sbds",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "Observing Block 'ob-1' not found in Project"

    def test_prjs_post_sbd_oda_error(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = IOError("test error")

        with pytest.raises(IOError):
            resp = client.post(
                f"{PRJS_API_URL}/prj-123/ob-1/sbds",
            )

            assert resp.json()["detail"] == "OSError('test error')"
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_prjs_post_sbd_success(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        obs_block_id = "ob-1"
        project.obs_blocks = [ObservingBlock(obs_block_id=obs_block_id)]
        sbd = TestDataFactory.sbdefinition()
        uow_mock.prjs.get.return_value = project
        uow_mock.sbds.add.return_value = sbd

        resp = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/{obs_block_id}/sbds",
        )

        assert resp.status_code == HTTPStatus.OK

        expected_response = {
            "sbd": sbd.model_dump(mode="json"),
            "prj": project.model_dump(mode="json"),
        }
        assert expected_response == resp.json()

        args, _ = uow_mock.sbds.add.call_args
        assert args[0].ob_ref == obs_block_id


class TestProjectGenerateSBDefinitions:

    @mock.patch("ska_oso_services.odt.api.prjs.generate_sbds")
    def test_prjs_post_generate_sbd_success(self, mock_generate_sbds, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        obs_block_id = "ob-1"
        project.obs_blocks = [ObservingBlock(obs_block_id=obs_block_id)]
        sbd = TestDataFactory.sbdefinition(ob_ref=obs_block_id)
        uow_mock.prjs.get.return_value = project
        uow_mock.sbds.add.return_value = sbd

        mock_generate_sbds.return_value = [sbd]

        response = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/generateSBDefinitions",
        )

        assert response.status_code == HTTPStatus.OK

        uow_mock.sbds.add.assert_called_once()
        args, _ = uow_mock.sbds.add.call_args
        assert args[0].ob_ref == obs_block_id
        assert_json_is_equal(response.text, project.model_dump_json())

    def test_prjs_post_generate_sbd_prj_id_not_found(self, client_with_uow_mock):
        """ """
        prj_id = "prj-999"
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ODANotFound(identifier=prj_id)

        resp = client.post(
            f"{PRJS_API_URL}/{prj_id}/generateSBDefinitions",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == f"The requested identifier {prj_id} could not be found."

    def test_prjs_post_generate_sbd_oda_error(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = IOError("test error")

        with pytest.raises(IOError):
            resp = client.post(
                f"{PRJS_API_URL}/prj-123/generateSBDefinitions",
            )

            assert resp.json()["detail"] == "OSError('test error')"
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectObsBlockGenerateSBDefinitions:

    @mock.patch("ska_oso_services.odt.api.prjs.generate_sbds")
    def test_prjs_post_ob_generate_sbd_success(self, mock_generate_sbds, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        obs_block_id = "ob-1"
        project.obs_blocks = [ObservingBlock(obs_block_id=obs_block_id)]
        sbd = TestDataFactory.sbdefinition(ob_ref=obs_block_id)
        uow_mock.prjs.get.return_value = project
        uow_mock.sbds.add.return_value = sbd

        mock_generate_sbds.return_value = [sbd]

        resp = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/{obs_block_id}/generateSBDefinitions",
        )

        assert resp.status_code == HTTPStatus.OK
        args, _ = uow_mock.sbds.add.call_args
        assert args[0].ob_ref == obs_block_id

    def test_prjs_post_ob_generate_sbd_prj_id_not_found(self, client_with_uow_mock):
        """ """
        prj_id = "prj-999"
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = ODANotFound(identifier=prj_id)

        resp = client.post(
            f"{PRJS_API_URL}/{prj_id}/obs-block-00001/generateSBDefinitions",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == f"The requested identifier {prj_id} could not be found."

    def test_prjs_post_ob_generate_sbd_obs_block_id_not_found(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        project = TestDataFactory.project()
        project.obs_blocks = []
        uow_mock.prjs.get.return_value = project

        resp = client.post(
            f"{PRJS_API_URL}/{project.prj_id}/obs-block-00001/generateSBDefinitions",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "Observing Block 'obs-block-00001' not found in Project"

    def test_prjs_post_ob_generate_sbd_oda_error(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        uow_mock.prjs.get.side_effect = IOError("test error")

        with pytest.raises(IOError):
            resp = client.post(
                f"{PRJS_API_URL}/prj-123/obs-block-00001/generateSBDefinitions",
            )

            assert resp.json()["detail"] == "OSError('test error')"
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestProjectDeleteObservingBlock:
    def test_delete_observing_block_success(self, client_with_uow_mock):
        """
        Check DELETE /prjs/{prj_id}/{obs_block_id} removes the OB and returns updated Project.
        """
        client, uow_mock = client_with_uow_mock
        prj_id = "prj-1234"
        obs_block_id = "ob-5678"
        updated_project = TestDataFactory.project(prj_id=prj_id)
        updated_project.obs_blocks = []
        uow_mock.prjs.delete_observing_block.return_value = None
        uow_mock.prjs.get.return_value = updated_project

        resp = client.delete(f"{PRJS_API_URL}/{prj_id}/{obs_block_id}")
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, updated_project.model_dump_json())
        uow_mock.prjs.delete_observing_block.assert_called_once_with(prj_id, obs_block_id)

    def test_delete_observing_integrity_error(self, client_with_uow_mock):
        """
        Check DELETE /prjs/{prj_id}/not-an-ob returns 422 if the ODA method
        raises an ODAIntegrityError.
        """
        client, uow_mock = client_with_uow_mock
        prj_id = "prj-1234"
        bad_ob_id = "not-an-ob"
        uow_mock.prjs.delete_observing_block.side_effect = ODAIntegrityError(
            "ob not linked to prj"
        )

        resp = client.delete(f"{PRJS_API_URL}/{prj_id}/{bad_ob_id}")
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "ob not linked to prj" in resp.json()["detail"]
