import json
import uuid
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

from ska_db_oda.persistence.domain.errors import ODANotFound, UniqueConstraintViolation
from ska_oso_pdm.proposal_management.panel import Panel

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory

PANELS_API_URL = f"{PHT_BASE_API_URL}/panels"
HEADERS = {"Content-type": "application/json"}


class TestPanelsUpdateAPI:
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_success(self, mock_uow, client):
        """
        PUT returns the panel_id when body.path IDs match and reviewer exists.
        """
        uow_mock = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow_mock

        panel_id = "panel-test-123"
        panel_obj = TestDataFactory.panel(
            panel_id=panel_id, name="Stargazers", reviewer_id=REVIEWERS[0]["id"]
        )

        uow_mock.panels.add.return_value = panel_obj

        resp = client.put(
            f"{PANELS_API_URL}/{panel_id}",
            data=panel_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == panel_id
        uow_mock.panels.add.assert_called_once()
        uow_mock.commit.assert_called_once()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_path_body_mismatch_returns_422(self, mock_uow, client):
        """
        If panel_id in path != body.panel_id -> UnprocessableEntityError
        """
        uow_mock = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow_mock

        body_panel_id = "panel-body-abc"
        path_panel_id = "panel-path-xyz"
        panel_obj = TestDataFactory.panel(
            panel_id=body_panel_id, name="Mismatch", reviewer_id=REVIEWERS[0]["id"]
        )

        resp = client.put(
            f"{PANELS_API_URL}/{path_panel_id}",
            data=panel_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY  # 422
        assert "do not match" in resp.json().get("detail", "").lower()
        uow_mock.panels.add.assert_not_called()
        uow_mock.commit.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_unknown_reviewer_returns_400(self, mock_uow, client):
        """
        If a reviewer in the body doesn't exist in REVIEWERS .
        """
        uow_mock = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow_mock

        panel_id = "panel-test-111"
        panel_obj = TestDataFactory.panel(
            panel_id=panel_id, name="BadReviewers", reviewer_id="rev-001"
        )

        resp = client.put(
            f"{PANELS_API_URL}/{panel_id}",
            data=panel_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "does not exist" in resp.json().get("detail", "").lower()
        uow_mock.panels.add.assert_not_called()
        uow_mock.commit.assert_not_called()


class TestPanelsAPI:
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_panels_post_success(self, mock_uow, client):
        panel = TestDataFactory.panel_basic(
            panel_id=f"panel-test-{uuid.uuid4().hex[:8]}", name="Galaxy"
        )

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
        panel = TestDataFactory.panel_basic(
            name="dup name", panel_id="panel-dup-name-20250616-00001"
        )

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
        expected = {
            "detail": "Duplicate prsl_id are not allowed: {'prsl-mvp01-20220923-00001'}"
        }
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
        expected = {"detail": "Proposal 'prsl-mvp01-20220923-00001' does not exist"}
        assert expected == result

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_get_panel_success(self, mock_oda, client):
        """
        Ensure valid panel ID returns the Panel object.
        """
        panel = TestDataFactory.panel()
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


class TestPanelAutoCreateAPI:

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.utils.pht_handler.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.upsert_panel")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.build_panel_response")
    def test_auto_create_panel_sv_success(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
    ):
        # Create a real Panel object

        panel_obj = Panel(
            panel_id="panel-888",
            name="Science Verification",
            reviewers=[],
            proposals=[],
        )

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.return_value = panel_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        payload = {"name": "Science Verification", "reviewers": [], "proposals": []}

        response = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )
        print("Response JSON:", response.json())
        assert response.status_code == HTTPStatus.OK
        panel_id = response.json()
        assert isinstance(panel_id, str)
        assert panel_id == "panel-888"

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.utils.pht_handler.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.upsert_panel")
    @mock.patch("ska_oso_services.pht.utils.panel_helper.build_panel_response")
    def test_auto_create_panel_category_success(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
    ):
        uow_mock = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow_mock

        # using 'Galaxy' that does not exist as part of science categories
        mock_build_panel_response.return_value = [
            {
                "panel_id": "panel-galaxy",
                "name": "Galaxy",
                "proposal_count": 0,
            },
        ]

        uow_mock.prsls.query.return_value = []
        uow_mock.panels.query.return_value = []
        mock_get_latest_entity_by_id.return_value = []
        mock_build_sv_panel_proposals.return_value = []

        def upsert_panel_side_effect(uow, panel_name, reviewers, proposals):
            proposals = proposals or []
            reviewers = reviewers or []
            return SimpleNamespace(
                panel_id=f"panel-{panel_name.lower().replace(' ', '-')}",
                name=panel_name,
                proposals=proposals,
                reviewers=reviewers,
            )

        mock_upsert_panel.side_effect = upsert_panel_side_effect

        uow_mock.panels.add.side_effect = lambda *a, **k: SimpleNamespace(
            panel_id="panel-galaxy",
            name="Galaxy",
            proposals=[],
            reviewers=[],
        )

        payload = {
            "name": "Galaxy",
            "reviewers": [],
            "proposals": [],
        }

        response = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert isinstance(result, list)

        panel_names = [panel["name"] for panel in result]
        assert "Cosmology" in panel_names
        assert all(panel["panel_id"] == "panel-galaxy" for panel in result)
        assert all(panel["proposal_count"] == 0 for panel in result)
        uow_mock.commit.assert_called_once()
