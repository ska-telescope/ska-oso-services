from http import HTTPStatus
from unittest import mock

from ska_db_oda.persistence.domain.errors import ODANotFound, UniqueConstraintViolation

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory

PANELS_API_URL = f"{PHT_BASE_API_URL}/panels"
HEADERS = {"Content-type": "application/json"}


class TestPanelsAPI:
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_success(self, mock_uow, client):
        panel = TestDataFactory.panel_basic()

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.OK

        result = response.json()
        assert panel.panel_id == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_duplicate_name(self, mock_uow, client):
        panel = TestDataFactory.panel_basic(name="dup name")

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.side_effect = UniqueConstraintViolation(
            "You name is duplicated"
        )
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        result = response.json()
        expected = {"detail": "You name is duplicated"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_duplicate_reviewer(self, mock_uow, client):
        panel = TestDataFactory.panel()
        panel.reviewers.append(panel.reviewers[0])

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.CONFLICT

        result = response.json()
        expected = {"detail": "Duplicate reviewer_id are not allowed: {'rev-001'}"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_duplicate_proposal(self, mock_uow, client):
        panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])
        panel.proposals.append(panel.proposals[0])

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.CONFLICT

        result = response.json()
        expected = {"detail": "Duplicate prsl_id are not allowed: {'prop-astro-01'}"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_not_existing_reviewer(self, mock_uow, client):
        panel = TestDataFactory.panel()

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        result = response.json()
        expected = {"detail": "Reviewer 'rev-001' does not exist"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_not_existing_proposal(self, mock_uow, client):
        panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel
        uow_mock.prsls.get.side_effect = ODANotFound
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        result = response.json()
        expected = {"detail": "Proposal 'prop-astro-01' does not exist"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_get_panel_success(self, mock_oda, client):
        """
        Ensure valid panel ID returns the Panel object.
        """
        panel = TestDataFactory.panel(panel_id="panel-Galactic-2025.2")
        panel_id = panel.panel_id

        uow_mock = mock.MagicMock()
        uow_mock.panels.get.return_value = panel
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PANELS_API_URL}/{panel_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["panel_id"] == panel_id

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_get_panel_list_success(self, mock_oda, client):
        """
        Check if the get_panels_for_user returns panels correctly.
        """
        panels_objs = [TestDataFactory.panel(), TestDataFactory.panel()]
        uow_mock = mock.MagicMock()
        uow_mock.panels.query.return_value = panels_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "DefaultUser"
        response = client.get(f"{PANELS_API_URL}/list/{user_id}")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == len(panels_objs)
