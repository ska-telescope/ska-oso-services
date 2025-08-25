"""
Unit tests for ska_oso_services.api
"""

import json
from http import HTTPStatus
from unittest import mock

import pytest
from ska_aaa_authhelpers.test_helpers import TEST_USER
from ska_db_oda.persistence.domain.errors import ODANotFound

from ska_oso_services.odt.api.prsls import ProposalProjectDetails
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
        uow_mock.prjs.add.assert_called_with(project, user=TEST_USER)

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


class TestProposalAndProjectView:

    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_proposal_without_project_returned_successfully(self, mock_uow, client):
        uow_mock = mock.MagicMock()
        proposal = TestDataFactory.complete_proposal()
        uow_mock.prsls.query.return_value = [proposal]

        uow_mock.prjs.query.return_value = []

        mock_uow().__enter__.return_value = uow_mock

        resp = client.get(
            f"{PRSLS_API_URL}/project-view",
        )

        assert resp.status_code == HTTPStatus.OK
        result = resp.json()

        assert len(result) == 1
        # Dump to json then load so the datetimes are serialised
        assert result[0] == json.loads(
            ProposalProjectDetails(
                prj_id=None,
                prsl_id=proposal.prsl_id,
                prsl_version=1,
                title=proposal.info.title,
                last_modified_by=proposal.metadata.last_modified_by,
                last_modified_on=proposal.metadata.last_modified_on,
                created_by=proposal.metadata.created_by,
                created_on=proposal.metadata.created_on,
            ).model_dump_json()
        )

    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_project_and_proposal_returned_successfully(self, mock_uow, client):
        uow_mock = mock.MagicMock()
        proposal = TestDataFactory.complete_proposal()
        uow_mock.prsls.query.return_value = [proposal]

        project = TestDataFactory.project()
        project.prsl_ref = proposal.prsl_id
        uow_mock.prjs.query.return_value = [project]

        mock_uow().__enter__.return_value = uow_mock

        resp = client.get(
            f"{PRSLS_API_URL}/project-view",
        )

        assert resp.status_code == HTTPStatus.OK
        result = resp.json()

        assert len(result) == 1
        # Dump to json then load so the datetimes are serialised
        assert result[0] == json.loads(
            ProposalProjectDetails(
                prj_id=project.prj_id,
                prj_version=1,
                prsl_id=proposal.prsl_id,
                title=project.name,
                last_modified_by=project.metadata.last_modified_by,
                last_modified_on=project.metadata.last_modified_on,
                created_by=project.metadata.created_by,
                created_on=project.metadata.created_on,
            ).model_dump_json()
        )

    @mock.patch("ska_oso_services.odt.api.prsls.oda.uow")
    def test_project_without_proposal_returned_successfully(self, mock_uow, client):
        uow_mock = mock.MagicMock()

        uow_mock.prsls.query.return_value = []

        project = TestDataFactory.project()
        uow_mock.prjs.query.return_value = [project]

        mock_uow().__enter__.return_value = uow_mock

        resp = client.get(
            f"{PRSLS_API_URL}/project-view",
        )

        assert resp.status_code == HTTPStatus.OK
        result = resp.json()

        assert len(result) == 1
        # Dump to json then load so the datetimes are serialised
        assert result[0] == json.loads(
            ProposalProjectDetails(
                prj_id=project.prj_id,
                prj_version=1,
                prsl_id=None,
                title=project.name,
                last_modified_by=project.metadata.last_modified_by,
                last_modified_on=project.metadata.last_modified_on,
                created_by=project.metadata.created_by,
                created_on=project.metadata.created_on,
            ).model_dump_json()
        )
