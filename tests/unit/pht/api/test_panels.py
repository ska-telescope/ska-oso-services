import json
import logging
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

from ska_db_oda.persistence.domain.errors import UniqueConstraintViolation
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.pht.api import panels as panels_api
from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory, assert_json_is_equal

PANELS_API_URL = f"{PHT_BASE_API_URL}/panels"
HEADERS = {"Content-type": "application/json"}


class TestPanelsUpdateAPI:
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_id_mismatch_returns_422(self, mock_uow, client):
        """
        If body.panel_id != path panel_id -> 422.
        """
        body_panel = TestDataFactory.panel(
            panel_id="panel-ABC",
            name="Cosmology",
        )

        path_id = "panel-XYZ"  # mismatch

        resp = client.put(
            f"{PANELS_API_URL}/{path_id}",
            data=body_panel.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in resp.text.lower()

        mock_uow().__enter__.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_success(self, mock_uow, client):
        """
        Returns the panel object when body.path IDs match and reviewer exists.
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
        assert_json_is_equal(resp.text, panel_obj.model_dump_json())
        uow_mock.panels.add.assert_called_once()
        uow_mock.commit.assert_called_once()

    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.generate_entity_id", autospec=True)
    @mock.patch(
        "ska_oso_services.pht.api.panels.get_latest_entity_by_id", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_creates_technical_review_when_missing(
        self, mock_uow, mock_get_latest, mock_gen_id, mock_validate, client
    ):
        """
        With a technical reviewer and no existing technical review
        for (proposal, reviewer):
        - create a Technical Review,
        - persist the panel,
        - return the panel object.
        """
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        # No existing technical review
        mock_get_latest.return_value = []

        mock_gen_id.return_value = "rvs-tec-0001"

        assigned_on = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

        tech = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-001", assigned_on=assigned_on
        )
        prop_assign = TestDataFactory.proposal_assignment(
            prsl_id="prsl-001", assigned_on=assigned_on
        )

        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-123",
            name="Cosmology",
            sci_reviewers=[],
            tech_reviewers=[tech],
            proposals=[prop_assign],
        )

        uow.panels.add.side_effect = lambda p: p

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        # Dedup validation called
        mock_validate.assert_called_once()

        # One technical review created
        uow.rvws.add.assert_called_once()
        created_review = uow.rvws.add.call_args[0][0]
        assert getattr(created_review, "prsl_id", None) == "prsl-001"
        assert getattr(created_review, "reviewer_id", None) == "rev-001"

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.generate_entity_id",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.get_latest_entity_by_id",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_skips_creating_tech_review_if_already_exists_v1(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow
        mock_gen_id_ops.return_value = "pnld-123"

        # Ref already indicates version==1 (so helper should skip creation)
        existing_ref = SimpleNamespace(
            review_id="rvw-existing",
            reviewer_id="rev-001",
            metadata=SimpleNamespace(version=1),
        )
        mock_get_latest_ops.return_value = [existing_ref]

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tech = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(
            prsl_id="prsl-001", assigned_on=assigned_on
        )
        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-123",
            name="Cosmology",
            sci_reviewers=[],
            tech_reviewers=[tech],
            proposals=[prop],
        )

        uow.panels.add.side_effect = lambda p: p

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        mock_validate.assert_called_once()
        # Because version==1 exists, helper should not create a new review:
        uow.rvws.add.assert_not_called()
        uow.pnlds.add.assert_called_once()
        mock_gen_id_ops.assert_called_once()  # called for decision, not tech review
        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.generate_entity_id",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.get_latest_entity_by_id",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_skips_creating_decision_if_already_exists(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        # Ref already indicates version==1 (so helper should skip creation)
        existing_decision_ref = SimpleNamespace(
            panel_id="panel-existing",
            decision_id="pnld-001",
            cycle="science verification",
            prsl_id="prsl-001",
            metadata=SimpleNamespace(version=1),
        )
        mock_get_latest_ops.return_value = [existing_decision_ref]

        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-existing",
            name="Cosmology",
        )

        uow.panels.add.side_effect = lambda p: p

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        mock_validate.assert_called_once()
        # Because version==1 exists, helper should not create a new review:
        uow.pnlds.add.assert_not_called()
        uow.rvws.add.assert_not_called()
        mock_gen_id_ops.assert_not_called()
        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.generate_entity_id",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.get_latest_entity_by_id",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_creates_decision_and_science_review_when_missing(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        # No existing decision for (proposal)
        mock_get_latest_ops.return_value = []

        # Deterministic ID for decision
        mock_gen_id_ops.return_value = "pnld-0001"

        # Repos return passed object (upsert-like)
        uow.pnlds.add.side_effect = lambda r: r
        uow.panels.add.side_effect = lambda p: p

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-sci-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(
            prsl_id="prsl-001", assigned_on=assigned_on
        )
        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-123",
            name="Cosmology",
            sci_reviewers=[sci],
            tech_reviewers=[],
            proposals=[prop],
        )

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        mock_validate.assert_called_once()
        uow.rvws.add.assert_called_once()
        uow.pnlds.add.assert_called_once()

        created = uow.pnlds.add.call_args[0][0]
        assert created.decision_id == "pnld-0001"
        assert created.prsl_id == "prsl-001"
        assert (
            mock_gen_id_ops.call_count == 2
        )  # called once for decision generation & once for science review generation

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.generate_entity_id",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.get_latest_entity_by_id",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_creates_science_review_when_missing(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        # No existing science review for (proposal, reviewer, kind)
        mock_get_latest_ops.return_value = []

        # Deterministic ID for science review
        mock_gen_id_ops.return_value = "rvs-sci-0001"

        # Repos return passed object (upsert-like)
        uow.rvws.add.side_effect = lambda r: r
        uow.panels.add.side_effect = lambda p: p

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-sci-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(
            prsl_id="prsl-001", assigned_on=assigned_on
        )
        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-123",
            name="Cosmology",
            sci_reviewers=[sci],
            tech_reviewers=[],
            proposals=[prop],
        )

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        mock_validate.assert_called_once()
        uow.rvws.add.assert_called_once()

        created = uow.rvws.add.call_args[0][0]
        assert created.review_id == "rvs-sci-0001"
        assert created.prsl_id == "prsl-001"
        assert created.reviewer_id == "rev-sci-001"

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.generate_entity_id",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.panel_operations.get_latest_entity_by_id",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.panels.validate_duplicates", autospec=True)
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_skips_creating_science_review_if_already_exists_v1(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):

        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow
        mock_gen_id_ops.return_value = "pnld-123"

        # Ref already indicates metadata.version == 1 → helper should skip creation
        existing_ref = SimpleNamespace(
            review_id="rvw-existing-sci",
            reviewer_id="rev-sci-001",
            metadata=SimpleNamespace(version=1),
        )
        mock_get_latest_ops.return_value = [existing_ref]

        uow.panels.add.side_effect = lambda p: p

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-sci-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(
            prsl_id="prsl-001", assigned_on=assigned_on
        )
        panel_body = TestDataFactory.panel_with_assignment(
            panel_id="panel-123",
            name="Cosmology",
            sci_reviewers=[sci],
            tech_reviewers=[],
            proposals=[prop],
        )

        resp = client.put(
            f"{PANELS_API_URL}/{panel_body.panel_id}",
            data=panel_body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.OK
        assert_json_is_equal(resp.text, panel_body.model_dump_json())

        mock_validate.assert_called_once()
        uow.rvws.add.assert_not_called()
        uow.pnlds.add.assert_called_once()
        mock_gen_id_ops.assert_called_once()  # called for decision, not science review
        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

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

        response = client.post(f"{PANELS_API_URL}/create", data=data, headers=HEADERS)

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

        response = client.post(f"{PANELS_API_URL}/create", data=data, headers=HEADERS)

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

        response = client.get(f"{PANELS_API_URL}/")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1


class TestPanelAutoCreateAPI:

    # ─────────────────────────────────────────────────────────────────────────
    # SV: No existing SV panel --> create panel (even if no submitted)
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
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
        mock_ensure_under_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # 1) submitted proposals -> []
        # 2) existing SV panel   -> []
        mock_get_latest_entity_by_id.side_effect = [[], []]
        mock_build_sv_panel_proposals.return_value = []

        uow.panels.add.return_value = TestDataFactory.panel_basic(
            panel_id="panel-888", name="Science Verification"
        )

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-888"

        mock_upsert_panel.assert_not_called()
        mock_build_panel_response.assert_not_called()
        mock_build_sv_panel_proposals.assert_called_once_with([])

        added_panel = uow.panels.add.call_args[0][0]
        assert getattr(added_panel, "name") == "Science Verification"
        mock_ensure_under_review.assert_called_once()
        uow.commit.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────
    # Category panels (non-SV): No submitted --> upsert empty groups
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
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
        mock_ensure_under_review,
        client,
        monkeypatch,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # deterministic pool
        monkeypatch.setattr(
            panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True
        )

        # No submitted proposals --> upsert gets []
        mock_get_latest_entity_by_id.return_value = []

        def upsert_panel_side_effect(*args, **kwargs):
            name = kwargs.get("panel_name") or (args[1] if len(args) > 1 else None)
            return TestDataFactory.panel_basic(
                panel_id=f"panel-{name.lower()}", name=name
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

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content

        result = resp.json()
        assert {p["name"] for p in result} == {"Cosmology", "Stars"}
        assert all(p["proposal_count"] == 0 for p in result)

        assert mock_upsert_panel.call_count == 2
        for call in mock_upsert_panel.call_args_list:
            _, kwargs = call
            assert kwargs["uow"] is uow
            assert kwargs["panel_name"] in {"Cosmology", "Stars"}
            assert kwargs["science_reviewers"] == []
            assert kwargs["technical_reviewers"] == []
            assert kwargs["proposals"] == []

        mock_build_sv_panel_proposals.assert_not_called()
        mock_build_panel_response.assert_called_once()
        mock_ensure_under_review.assert_called_once()
        uow.commit.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────
    # SV: Existing panel present & nothing to do --> early return (no writes)
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
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
        mock_ensure_under_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # 1) submitted proposals -> []
        # 2) existing SV panel present -> "panel-existing-sv"
        mock_get_latest_entity_by_id.side_effect = [
            [],
            [
                SimpleNamespace(
                    panel_id="panel-existing-sv", sci_reviewers=[], tech_reviewers=[]
                )
            ],
        ]

        payload = {
            "name": "   science verification   ",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-existing-sv"

        uow.panels.add.assert_not_called()
        uow.commit.assert_not_called()
        mock_build_sv_panel_proposals.assert_not_called()
        mock_upsert_panel.assert_not_called()
        mock_build_panel_response.assert_not_called()
        mock_ensure_under_review.assert_not_called()

    # ─────────────────────────────────────────────────────────────────────────
    # Create new panel with submitted proposals --> statuses set to UNDER_REVIEW
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    def test_auto_create_panel_sv_updates_proposals_to_under_review(
        self,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_uow,
        mock_ensure_under_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        submitted_refs = [
            SimpleNamespace(prsl_id="prop-1"),
            SimpleNamespace(prsl_id="prop-2"),
        ]
        # 1) submitted proposals
        # 2) no existing SV panel -> create
        mock_get_latest_entity_by_id.side_effect = [submitted_refs, []]
        mock_build_sv_panel_proposals.return_value = []

        uow.panels.add.return_value = TestDataFactory.panel_basic(
            panel_id="panel-new-sv", name="Science Verification"
        )

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-new-sv"

        # The endpoint should perform status updates to the helper once
        assert mock_ensure_under_review.call_count == 1
        args, _ = mock_ensure_under_review.call_args

        assert args[0] is uow
        prsl_ids = list(args[2])
        assert prsl_ids == ["prop-1", "prop-2"]

        uow.commit.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────
    # Category panels: Grouping & passing only matched categories to upsert_panel
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.upsert_panel")
    @mock.patch("ska_oso_services.pht.api.panels.build_panel_response")
    def test_auto_create_panel_category_groups_and_passes_proposals(
        self,
        mock_build_panel_response,
        mock_upsert_panel,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        mock_ensure_under_review,
        client,
        monkeypatch,
    ):
        """
        Ensure proposals are grouped by science_category and
        passed through to upsert_panel for each panel in PANEL_NAME_POOL;
        unmatched categories are skipped.
        """
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # Arrange proposals with categories (two matched, one unmatched)
        p_cosmology = TestDataFactory.proposal_by_category("prsl-1", "Cosmology")
        p_stars = TestDataFactory.proposal_by_category("prsl-2", "Stars")
        p_unknown = TestDataFactory.proposal_by_category("prsl-3", "Unknown")

        # 1) submitted proposals (used for grouping)
        mock_get_latest_entity_by_id.return_value = [p_cosmology, p_stars, p_unknown]

        monkeypatch.setattr(
            panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True
        )
        mock_build_panel_response.return_value = [
            {"panel_id": "panel-cosmology", "name": "Cosmology", "proposal_count": 1},
            {"panel_id": "panel-stars", "name": "Stars", "proposal_count": 1},
        ]

        calls = []

        def upsert_panel_capture(**kwargs):
            calls.append(
                (
                    kwargs["panel_name"],
                    [getattr(p, "prsl_id") for p in kwargs["proposals"]],
                )
            )
            return TestDataFactory.panel_basic(
                panel_id=f"panel-{kwargs['panel_name'].lower()}",
                name=kwargs["panel_name"],
            )

        mock_upsert_panel.side_effect = upsert_panel_capture

        payload = {
            "name": "Any non-SV name",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content

        assert mock_upsert_panel.call_count == 2
        assert ("Cosmology", ["prsl-1"]) in calls
        assert ("Stars", ["prsl-2"]) in calls
        assert all("prsl-3" not in ids for _, ids in calls)

        mock_build_sv_panel_proposals.assert_not_called()
        mock_build_panel_response.assert_called_once()
        mock_ensure_under_review.assert_called_once()
        uow.commit.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────
    # SV: Existing panel + submitted --> append only NEW assignments and update status
    # ─────────────────────────────────────────────────────────────────────────

    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    def test_auto_create_panel_sv_existing_appends_only_new_and_sets_status_for_new(
        self,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        mock_ensure_under_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # submitted proposals includes prop-1 & prop-2
        submitted_refs = [
            SimpleNamespace(prsl_id="prop-1"),
            SimpleNamespace(prsl_id="prop-2"),
        ]
        # existing SV panel present
        mock_get_latest_entity_by_id.side_effect = [
            submitted_refs,
            [
                SimpleNamespace(
                    panel_id="panel-existing-sv", sci_reviewers=[], tech_reviewers=[]
                )
            ],
        ]

        existing_assignment = TestDataFactory.proposal_assignment(
            prsl_id="prop-1", assigned_on=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        existing_panel = TestDataFactory.panel_with_assignment(
            panel_id="panel-existing-sv",
            name="Science Verification",
            proposals=[existing_assignment],
        )
        uow.panels.get.return_value = existing_panel

        a1 = TestDataFactory.proposal_assignment(
            prsl_id="prop-1", assigned_on=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )
        a2 = TestDataFactory.proposal_assignment(
            prsl_id="prop-2", assigned_on=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )
        mock_build_sv_panel_proposals.return_value = [a1, a2]

        captured_ids: list[str] = []

        def _ensure_side_effect(_uow, _auth, ids_iter):
            captured_ids.extend(list(ids_iter))
            return None

        mock_ensure_under_review.side_effect = _ensure_side_effect

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [],
            "tech_reviewers": [],
            "proposals": [],
        }

        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-existing-sv"

        # only prop-2 should be appended
        added_panel = uow.panels.add.call_args[0][0]
        panel_ids = [p.prsl_id for p in (added_panel.proposals or [])]
        assert panel_ids.count("prop-1") == 1
        assert "prop-2" in panel_ids

        # ensure status update requested only for newly added ID
        assert captured_ids == ["prop-2"]

        uow.commit.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────
    # SV: Existing panel, no submitted, reviewer lists provided --> update reviewers
    # ─────────────────────────────────────────────────────────────────────────
    @mock.patch(
        "ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review"
    )
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    def test_auto_create_panel_sv_existing_updates_reviewers_only(
        self,
        mock_build_sv_panel_proposals,
        mock_get_latest_entity_by_id,
        mock_oda,
        mock_ensure_under_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_oda.return_value.__enter__.return_value = uow

        # 1) submitted proposals -> []
        # 2) existing SV panel present
        mock_get_latest_entity_by_id.side_effect = [
            [],
            [
                SimpleNamespace(
                    panel_id="panel-existing-sv",
                    name="Science Verification",
                    sci_reviewers=[],
                    tech_reviewers=[],
                )
            ],
        ]

        mock_build_sv_panel_proposals.return_value = []

        # Use a lightweight panel to avoid Pydantic assignment validation
        existing_panel = SimpleNamespace(
            panel_id="panel-existing-sv",
            name="Science Verification",
            proposals=[],
            sci_reviewers=[],
            tech_reviewers=[],
        )
        uow.panels.get.return_value = existing_panel

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="sci-1", assigned_on=assigned_on
        )
        tec = TestDataFactory.reviewer_assignment(
            reviewer_id="tec-1", assigned_on=assigned_on
        )

        payload = {
            "name": "Science Verification",
            "sci_reviewers": [sci.reviewer_id],
            "tech_reviewers": [tec.reviewer_id],
            "proposals": [],
        }
        resp = client.post(f"{PANELS_API_URL}/auto-create", json=payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-existing-sv"

        mock_build_sv_panel_proposals.assert_not_called()

        assert mock_get_latest_entity_by_id.call_count == 2

        mock_ensure_under_review.assert_not_called()
