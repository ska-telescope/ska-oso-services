import json
from http import HTTPStatus
from unittest import mock

from ska_aaa_authhelpers.test_helpers.constants import TEST_USER
from ska_db_oda.persistence.domain.errors import ODANotFound, UniqueConstraintViolation

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory

PROPOSAL_ACCESS_API_URL = f"{PHT_BASE_API_URL}/proposal-access"
HEADERS = {"Content-type": "application/json"}


class TestProposalAccessAPI:
    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow")
    def test_proposal_access_post_success(self, mock_uow, client):
        proposal_access = TestDataFactory.proposal_access()

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.add.return_value = proposal_access
        mock_uow().__enter__.return_value = uow_mock

        data = proposal_access.json()

        response = client.post(
            f"{PROPOSAL_ACCESS_API_URL}/create", data=data, headers=HEADERS
        )

        assert response.status_code == HTTPStatus.OK

        result = response.json()

        assert proposal_access.access_id == result

    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow")
    def test_proposal_access_post_duplicate_prsl_id_user_id_pair(
        self, mock_uow, client
    ):
        panel = TestDataFactory.proposal_access(prsl_id="dup prsl_id")

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.add.side_effect = UniqueConstraintViolation(
            "Your prsl_id, user_id pair is duplicated"
        )
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(
            f"{PROPOSAL_ACCESS_API_URL}/create", data=data, headers=HEADERS
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

        result = response.json()
        expected = {"detail": "Your prsl_id, user_id pair is duplicated"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow")
    def test_proposal_access_put_success(self, mock_uow, client):
        proposal_access = TestDataFactory.proposal_access()
        access_id = proposal_access.access_id

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.add.return_value = proposal_access
        mock_uow().__enter__.return_value = uow_mock

        data = proposal_access.json()

        response = client.put(
            f"{PROPOSAL_ACCESS_API_URL}/user/{access_id}", data=data, headers=HEADERS
        )

        assert response.status_code == HTTPStatus.OK

        result = response.json()

        assert json.loads(proposal_access.model_dump_json()) == result

    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow", autospec=True)
    def test_get_proposal_access_by_user_success(self, mock_oda, client):
        """
        Returns list of proposal access filter by User ID
        """
        proposal_access = [
            TestDataFactory.proposal_access(access_id="access_id1", prsl_id="prsl1"),
            TestDataFactory.proposal_access(access_id="access_id2", prsl_id="prsl2"),
        ]

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.query.return_value = proposal_access
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PROPOSAL_ACCESS_API_URL}/user")

        assert response.status_code == HTTPStatus.OK

        assert isinstance(response.json(), list)
        assert len(response.json()) == len(proposal_access)

    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow", autospec=True)
    def test_get_proposal_access_by_prsl_id_success(self, mock_oda, client):
        """
        Returns list of proposal access filter by Proposal ID
        """
        MOCK_PRSL_ID = "prsl1"
        proposal_access = [
            TestDataFactory.proposal_access(
                access_id="access_id1",
                prsl_id=MOCK_PRSL_ID,
                user_id=TEST_USER,
                role="Principal Investigator",
            ),
            TestDataFactory.proposal_access(
                access_id="access_id2",
                prsl_id=MOCK_PRSL_ID,
                user_id="mocked-user-id",
                role="Co-Investigator",
            ),
        ]

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.query.return_value = proposal_access
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PROPOSAL_ACCESS_API_URL}/{MOCK_PRSL_ID}")

        assert response.status_code == HTTPStatus.OK

        assert isinstance(response.json(), list)
        assert len(response.json()) == len(proposal_access)

    @mock.patch("ska_oso_services.pht.api.prslacc.oda.uow", autospec=True)
    def test_get_proposal_access_by_prsl_id_not_PI_forbidden(self, mock_oda, client):
        """
        Returns forbidden error when user is not PI of a proposal
        """

        MOCK_PRSL_ID = "prsl1"
        proposal_access = [
            TestDataFactory.proposal_access(
                access_id="access_id1", prsl_id=MOCK_PRSL_ID, role="Co-Investigator"
            ),
            TestDataFactory.proposal_access(
                access_id="access_id2", prsl_id=MOCK_PRSL_ID, role="Co-Investigator"
            ),
        ]

        uow_mock = mock.MagicMock()
        uow_mock.prslacc.query.side_effect = [[], proposal_access]
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PROPOSAL_ACCESS_API_URL}/{MOCK_PRSL_ID}")

        assert response.status_code == HTTPStatus.FORBIDDEN
