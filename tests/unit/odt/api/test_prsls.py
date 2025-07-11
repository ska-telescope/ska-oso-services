"""
Unit tests for ska_oso_services.api
"""

from http import HTTPStatus
from unittest import mock

import pytest
from ska_db_oda.persistence.domain.errors import ODANotFound

from tests.unit.conftest import ODT_BASE_API_URL
from tests.unit.util import TestDataFactory, assert_json_is_equal

PRSLS_API_URL = f"{ODT_BASE_API_URL}/prsls"


class TestProjectCreationFromProposal:

    @mock.patch("ska_oso_services.odt.api.prsls.generate_project")
    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_project_from_proposal_success(
        self, mock_uow, mock_generate_project, client
    ):
        """ """
        uow_mock = mock.MagicMock()
        proposal = TestDataFactory.proposal()
        uow_mock.prsls.get.return_value = proposal
        mock_uow().__enter__.return_value = uow_mock

        project = TestDataFactory.project()
        mock_generate_project.return_value = project
        uow_mock.prjs.add.return_value = project

        resp = client.post(
            f"{PRSLS_API_URL}/{proposal.prsl_id}/generateProject",
        )

        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, project.model_dump_json())
        uow_mock.prjs.add.assert_called_with(project)

    @mock.patch("ska_oso_services.odt.api.prsls.generate_project")
    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_project_status_is_created(self, mock_uow, mock_generate_project, client):
        """ """
        uow_mock = mock.MagicMock()
        proposal = TestDataFactory.proposal()
        uow_mock.prsls.get.return_value = proposal
        mock_uow().__enter__.return_value = uow_mock

        project = TestDataFactory.project()
        mock_generate_project.return_value = project
        uow_mock.prjs.add.return_value = project

        add_status_mock = mock.MagicMock()
        uow_mock.prjs_status_history.add = add_status_mock

        resp = client.post(
            f"{PRSLS_API_URL}/{proposal.prsl_id}/generateProject",
        )

        assert resp.status_code == HTTPStatus.OK
        add_status_mock.assert_called()

    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_proposal_not_found(self, mock_uow, client):
        """ """
        uow_mock = mock.MagicMock()
        prsl_id = "prsl-999"
        uow_mock.prsls.get.side_effect = ODANotFound(identifier=prsl_id)
        mock_uow().__enter__.return_value = uow_mock

        resp = client.post(
            f"{PRSLS_API_URL}/{prsl_id}/generateProject",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert (
            resp.json()["detail"]
            == f"The requested identifier {prsl_id} could not be found."
        )

    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_oda_error(self, mock_uow, client):
        """ """
        uow_mock = mock.MagicMock()
        proposal = TestDataFactory.proposal()
        uow_mock.prsls.get.side_effect = IOError("test error")
        mock_uow().__enter__.return_value = uow_mock
        with pytest.raises(IOError):
            response = client.post(
                f"{PRSLS_API_URL}/{proposal.prsl_id}/generateProject",
            )

            result = response.json()

            assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert result["title"] == "Internal Server Error"
            assert result["message"] == "OSError('test error')"
