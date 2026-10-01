"""
Unit tests for ska_oso_services.api
"""

import json
from http import HTTPStatus
from unittest import mock

import pytest
from ska_aaa_authhelpers.test_helpers import TEST_USER
from ska_db_oda.postgres.mapping import InternalStatus
from ska_db_oda.repository.domain import ODANotFound
from ska_oso_pdm.proposal.proposal import ProposalStatus

from ska_oso_services.odt.api.prsls import ProposalProjectDetails
from tests.conftest import ODT_BASE_API_URL
from tests.unit.util import TestDataFactory, assert_json_is_equal

PRSLS_API_URL = f"{ODT_BASE_API_URL}/prsls"


class TestProjectCreationFromProposal:
    @mock.patch("ska_oso_services.odt.api.prsls.generate_project")
    def test_project_from_proposal_success(self, mock_generate_project, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        proposal = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)
        uow_mock.prsls.get.return_value = proposal

        project = TestDataFactory.project()
        mock_generate_project.return_value = project
        uow_mock.prjs.add.return_value = project

        resp = client.post(
            f"{PRSLS_API_URL}/{proposal.prsl_id}/generateProject",
        )

        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, project.model_dump_json())
        uow_mock.prjs.add.assert_called_with(project, user=TEST_USER)

    def test_proposal_not_found(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        prsl_id = "prsl-999"
        uow_mock.prsls.get.side_effect = ODANotFound(identifier=prsl_id)

        resp = client.post(
            f"{PRSLS_API_URL}/{prsl_id}/generateProject",
        )

        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == f"The requested identifier {prsl_id} could not be found."

    def test_oda_error(self, client_with_uow_mock):
        """ """
        client, uow_mock = client_with_uow_mock
        proposal = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)
        uow_mock.prsls.get.side_effect = IOError("test error")

        with pytest.raises(IOError):
            response = client.post(
                f"{PRSLS_API_URL}/{proposal.prsl_id}/generateProject",
            )

            result = response.json()

            assert result["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
            assert result["title"] == "Internal Server Error"
            assert result["detail"] == "OSError('test error')"


class TestProposalAndProjectView:
    """prj_details now issues a single UNION ALL query via ``uow.execute()``, so
    these tests mock the raw dict rows that query would return, rather than
    per-repository ``.query()``/``.get_current_status()`` calls. Draft-proposal
    exclusion and "latest version only" are now enforced by the SQL itself
    (WHERE clause / single-row-per-id main tables), so they are no longer
    exercised at this mocked level.
    """

    def test_proposal_without_project_returned_successfully(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        proposal = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)
        uow_mock.execute.return_value = [
            {
                "prj_id": None,
                "prj_version": None,
                "prsl_id": proposal.prsl_id,
                "prsl_version": 1,
                "title": proposal.proposal_info.title,
                "prj_status": None,
                "prj_created_by": None,
                "prj_created_on": None,
                "prj_last_modified_by": None,
                "prj_last_modified_on": None,
            }
        ]

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
                title=proposal.proposal_info.title,
            ).model_dump_json()
        )

    def test_project_and_proposal_returned_successfully(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        proposal = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)

        project = TestDataFactory.project()
        project.prsl_ref = proposal.prsl_id
        uow_mock.execute.return_value = [
            {
                "prj_id": project.prj_id,
                "prj_version": 1,
                "prsl_id": proposal.prsl_id,
                "prsl_version": None,
                "title": project.name,
                "prj_status": InternalStatus.APPROVED,
                "prj_created_by": project.metadata.created_by,
                "prj_created_on": project.metadata.created_on,
                "prj_last_modified_by": project.metadata.last_modified_by,
                "prj_last_modified_on": project.metadata.last_modified_on,
            }
        ]

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
                prj_status="Ready",
                prj_last_modified_by=project.metadata.last_modified_by,
                prj_last_modified_on=project.metadata.last_modified_on,
                prj_created_by=project.metadata.created_by,
                prj_created_on=project.metadata.created_on,
            ).model_dump_json()
        )

    def test_project_without_proposal_returned_successfully(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock

        project = TestDataFactory.project()
        uow_mock.execute.return_value = [
            {
                "prj_id": project.prj_id,
                "prj_version": 1,
                "prsl_id": None,
                "prsl_version": None,
                "title": project.name,
                "prj_status": InternalStatus.APPROVED,
                "prj_created_by": project.metadata.created_by,
                "prj_created_on": project.metadata.created_on,
                "prj_last_modified_by": project.metadata.last_modified_by,
                "prj_last_modified_on": project.metadata.last_modified_on,
            }
        ]

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
                prj_status="Ready",
                prj_last_modified_by=project.metadata.last_modified_by,
                prj_last_modified_on=project.metadata.last_modified_on,
                prj_created_by=project.metadata.created_by,
                prj_created_on=project.metadata.created_on,
            ).model_dump_json()
        )

    def test_multiple_rows_returned_successfully(self, client_with_uow_mock):
        client, uow_mock = client_with_uow_mock
        proposal_with_prj = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)
        proposal_without_prj = TestDataFactory.complete_proposal(status=ProposalStatus.SUBMITTED)

        project = TestDataFactory.project()
        project.prsl_ref = proposal_with_prj.prsl_id
        uow_mock.execute.return_value = [
            {
                "prj_id": project.prj_id,
                "prj_version": 1,
                "prsl_id": proposal_with_prj.prsl_id,
                "prsl_version": None,
                "title": project.name,
                "prj_status": InternalStatus.APPROVED,
                "prj_created_by": project.metadata.created_by,
                "prj_created_on": project.metadata.created_on,
                "prj_last_modified_by": project.metadata.last_modified_by,
                "prj_last_modified_on": project.metadata.last_modified_on,
            },
            {
                "prj_id": None,
                "prj_version": None,
                "prsl_id": proposal_without_prj.prsl_id,
                "prsl_version": 1,
                "title": proposal_without_prj.proposal_info.title,
                "prj_status": None,
                "prj_created_by": None,
                "prj_created_on": None,
                "prj_last_modified_by": None,
                "prj_last_modified_on": None,
            },
        ]

        resp = client.get(
            f"{PRSLS_API_URL}/project-view",
        )

        assert resp.status_code == HTTPStatus.OK
        result = resp.json()

        assert len(result) == 2
        # Dump to json then load so the datetimes are serialised
        assert result[0] == json.loads(
            ProposalProjectDetails(
                prj_id=project.prj_id,
                prj_version=1,
                prsl_id=proposal_with_prj.prsl_id,
                title=project.name,
                prj_status="Ready",
                prj_last_modified_by=project.metadata.last_modified_by,
                prj_last_modified_on=project.metadata.last_modified_on,
                prj_created_by=project.metadata.created_by,
                prj_created_on=project.metadata.created_on,
            ).model_dump_json()
        )
        assert result[1] == json.loads(
            ProposalProjectDetails(
                prj_id=None,
                prsl_id=proposal_without_prj.prsl_id,
                prsl_version=1,
                title=proposal_without_prj.proposal_info.title,
            ).model_dump_json()
        )
