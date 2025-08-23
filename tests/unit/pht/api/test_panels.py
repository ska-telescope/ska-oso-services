import json
import uuid
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

from ska_db_oda.persistence.domain.errors import UniqueConstraintViolation
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.pht.api import panels as panels_api
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
            panel_id=panel_id,
            name="Stargazers",
            reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
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
            panel_id=body_panel_id,
            name="Mismatch",
            reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
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
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.upsert_panel")
    @mock.patch("ska_oso_services.pht.api.panels.build_panel_response")
    def test_auto_create_panel_sv_success(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
    ):
        panel_obj = TestDataFactory.panel_basic(
            panel_id="panel-888", name="Science Verification"
        )

        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        mock_get_latest_entity_by_id.side_effect = [[], []]
        mock_build_sv_panel_proposals.return_value = []

        uow.panels.add.return_value = panel_obj

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-888"

        mock_build_sv_panel_proposals.assert_called_once()
        added_panel = uow.panels.add.call_args[0][0]
        assert getattr(added_panel, "name") == "Science Verification"
        uow.commit.assert_called_once()
        mock_upsert_panel.assert_not_called()
        mock_build_panel_response.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.upsert_panel")
    @mock.patch("ska_oso_services.pht.api.panels.build_panel_response")
    def test_auto_create_panel_category_success(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
        monkeypatch,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        monkeypatch.setattr(
            panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True
        )

        mock_get_latest_entity_by_id.return_value = []

        def upsert_panel_side_effect(
            uow_, panel_name, sci_reviewers, tech_reviewers, proposals
        ):
            return TestDataFactory.panel_basic(
                panel_id=f"panel-{panel_name.lower()}", name=panel_name
            )

        mock_upsert_panel.side_effect = upsert_panel_side_effect

        mock_build_panel_response.return_value = [
            {"panel_id": "panel-cosmology", "name": "Cosmology", "proposal_count": 0},
            {"panel_id": "panel-stars", "name": "Stars", "proposal_count": 0},
        ]

        payload = {
            "name": "Galaxy",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        result = resp.json()
        assert isinstance(result, list)
        assert {p["name"] for p in result} == {"Cosmology", "Stars"}
        assert all(p["proposal_count"] == 0 for p in result)

        assert mock_upsert_panel.call_count == 2
        mock_build_panel_response.assert_called_once()
        uow.commit.assert_called_once()
        mock_build_sv_panel_proposals.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.upsert_panel")
    @mock.patch("ska_oso_services.pht.api.panels.build_panel_response")
    def test_auto_create_panel_sv_returns_existing(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        mock_get_latest_entity_by_id.side_effect = [
            [],
            [SimpleNamespace(panel_id="panel-existing-sv")],
        ]

        payload = {
            "name": "   science verification   ",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-existing-sv"

        uow.panels.add.assert_not_called()
        uow.commit.assert_not_called()
        mock_build_sv_panel_proposals.assert_not_called()
        mock_upsert_panel.assert_not_called()
        mock_build_panel_response.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    def test_auto_create_panel_sv_missing_proposal_raises_400(
        self,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        client,
        monkeypatch,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        submitted = [SimpleNamespace(prsl_id="prop-missing")]
        mock_get_latest_entity_by_id.side_effect = [submitted, []]

        mock_build_sv_panel_proposals.return_value = []

        uow.panels.add.return_value = TestDataFactory.panel_basic(
            panel_id="panel-new-sv", name="Science Verification"
        )

        class DummyNotFound(Exception):
            pass

        monkeypatch.setattr(panels_api, "ODANotFound", DummyNotFound, raising=False)
        uow.prsls.get.side_effect = DummyNotFound

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content
        uow.commit.assert_not_called()
        uow.prsls.get.assert_called_once_with("prop-missing")

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    def test_auto_create_panel_sv_updates_proposals_to_under_review(
        self,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_uow,
        client,
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        submitted_ids = [
            SimpleNamespace(prsl_id="prop-1"),
            SimpleNamespace(prsl_id="prop-2"),
        ]
        mock_get_latest_entity_by_id.side_effect = [submitted_ids, []]
        mock_build_sv_panel_proposals.return_value = []

        uow.panels.add.return_value = TestDataFactory.panel_basic(
            panel_id="panel-new-sv", name="Science Verification"
        )

        p1_db = SimpleNamespace(
            prsl_id="prop-1", status=panels_api.ProposalStatus.SUBMITTED
        )
        p2_db = SimpleNamespace(
            prsl_id="prop-2", status=panels_api.ProposalStatus.SUBMITTED
        )
        uow.prsls.get.side_effect = [p1_db, p2_db]

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(
            f"{PANELS_API_URL}/auto-create",
            json=payload,
            headers={"Content-type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-new-sv"

        assert uow.prsls.get.call_args_list == [
            mock.call("prop-1"),
            mock.call("prop-2"),
        ]

        assert p1_db.status == panels_api.ProposalStatus.UNDER_REVIEW
        assert p2_db.status == panels_api.ProposalStatus.UNDER_REVIEW
        assert uow.prsls.add.call_args_list == [mock.call(p1_db), mock.call(p2_db)]

        uow.commit.assert_called_once()
