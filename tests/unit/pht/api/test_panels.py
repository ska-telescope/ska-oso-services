import json
import logging
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

from ska_db_oda.persistence.domain.errors import UniqueConstraintViolation

from ska_oso_services.pht.api import panels as panels_api
from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory, assert_json_is_equal

PANELS_API_URL = f"{PHT_BASE_API_URL}/panels"
HEADERS = {"Content-type": "application/json"}
MODULE = "ska_oso_services.pht.api.panels"


class TestPanelsUpdateAPI:
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_id_mismatch_returns_422(self, mock_uow, client):
        """
        If body.panel_id != path panel_id -> 422.
        """
        body_panel = TestDataFactory.panel(
            panel_id="panel-ABC",
            name="Cosmology",
        )

        path_id = "panel-XYZ"

        resp = client.put(
            f"{PANELS_API_URL}/{path_id}",
            data=body_panel.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in resp.text.lower()

        mock_uow().__enter__.assert_not_called()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
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

    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.generate_entity_id", autospec=True)
    @mock.patch(f"{MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
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

        tech = TestDataFactory.reviewer_assignment(reviewer_id="rev-001", assigned_on=assigned_on)
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
    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_skips_creating_tech_review_if_already_exists_v1(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow
        mock_gen_id_ops.return_value = "pnld-123"

        existing_ref = SimpleNamespace(
            review_id="rvw-existing",
            reviewer_id="rev-001",
            metadata=SimpleNamespace(version=1),
        )
        mock_get_latest_ops.return_value = [existing_ref]

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tech = TestDataFactory.reviewer_assignment(reviewer_id="rev-001", assigned_on=assigned_on)
        prop = TestDataFactory.proposal_assignment(prsl_id="prsl-001", assigned_on=assigned_on)
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
        uow.rvws.add.assert_not_called()
        uow.pnlds.add.assert_called_once()
        mock_gen_id_ops.assert_called_once()
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
    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_skips_creating_decision_if_already_exists(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

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
    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_creates_decision_and_science_review_when_missing(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        mock_get_latest_ops.return_value = []

        mock_gen_id_ops.return_value = "pnld-0001"

        uow.pnlds.add.side_effect = lambda r: r
        uow.panels.add.side_effect = lambda p: p

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-sci-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(prsl_id="prsl-001", assigned_on=assigned_on)
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
        assert mock_gen_id_ops.call_count == 2

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
    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_creates_science_review_when_missing(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):
        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow

        mock_get_latest_ops.return_value = []

        mock_gen_id_ops.return_value = "rvs-sci-0001"

        uow.rvws.add.side_effect = lambda r: r
        uow.panels.add.side_effect = lambda p: p

        assigned_on = datetime(2025, 1, 1, tzinfo=timezone.utc)
        sci = TestDataFactory.reviewer_assignment(
            reviewer_id="rev-sci-001", assigned_on=assigned_on
        )
        prop = TestDataFactory.proposal_assignment(prsl_id="prsl-001", assigned_on=assigned_on)
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
    @mock.patch(f"{MODULE}.validate_duplicates", autospec=True)
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_skips_creating_science_review_if_already_exists_v1(
        self, mock_uow, mock_validate, mock_get_latest_ops, mock_gen_id_ops, client
    ):

        uow = mock.MagicMock()
        mock_uow().__enter__.return_value = uow
        mock_gen_id_ops.return_value = "pnld-123"

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
        prop = TestDataFactory.proposal_assignment(prsl_id="prsl-001", assigned_on=assigned_on)
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
        mock_gen_id_ops.assert_called_once()
        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch("ska_oso_services.pht.api.panels.oda.uow", autospec=True)
    def test_update_panel_path_body_mismatch_returns_422(self, mock_uow, client):
        """
        If panel_id in path != body.panel_id --> UnprocessableEntityError
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

        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in resp.json().get("detail", "").lower()
        uow_mock.panels.add.assert_not_called()
        uow_mock.commit.assert_not_called()


class TestPanelsAPI:
    @mock.patch(f"{MODULE}.oda.uow")
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

    @mock.patch(f"{MODULE}.oda.uow")
    def test_panels_post_duplicate_name(self, mock_uow, client):
        panel = TestDataFactory.panel_basic(
            name="dup name", panel_id="panel-dup-name-20250616-00001"
        )

        uow_mock = mock.MagicMock()
        uow_mock.panels.add.side_effect = UniqueConstraintViolation("You name is duplicated")
        mock_uow().__enter__.return_value = uow_mock

        data = panel.json()

        response = client.post(f"{PANELS_API_URL}/create", data=data, headers=HEADERS)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        result = response.json()
        expected_detail = "You name is duplicated"
        assert expected_detail == result["detail"]

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
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

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
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


class TestPanelsGenerateAPI:
    # SV: No existing SV panel -> create & return new id
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    def test_generate_sv_creates_when_missing(self, mock_get_latest, mock_uow, client):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        mock_get_latest.return_value = []  # SV not found
        uow.panels.add.return_value = SimpleNamespace(
            panel_id="panel-888", name="Science Verification"
        )

        resp = client.post(f"{PANELS_API_URL}/generate", params={"param": "Science Verification"})
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-888"

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()
        created_panel = uow.panels.add.call_args[0][0]
        assert created_panel.name == panels_api.SV_NAME

    # SV: Existing -> return existing id, no writes
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    def test_generate_sv_returns_existing_noop(self, mock_get_latest, mock_uow, client):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        mock_get_latest.return_value = [SimpleNamespace(panel_id="panel-existing-sv")]

        resp = client.post(f"{PANELS_API_URL}/generate", params={"param": "science verification"})
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-existing-sv"

        uow.panels.add.assert_not_called()
        uow.commit.assert_not_called()

    # Category: Creates only missing panels from PANEL_NAME_POOL
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    def test_generate_categories_creates_missing_only(
        self, mock_get_latest, mock_uow, client, monkeypatch
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        monkeypatch.setattr(
            panels_api,
            "PANEL_NAME_POOL",
            ["Cosmology", "Stars", "Transients"],
            raising=True,
        )

        # Cosmology exists; Stars + Transients missing
        mock_get_latest.side_effect = [
            [SimpleNamespace(panel_id="panel-cosmology")],
            [],
            [],
        ]

        resp = client.post(f"{PANELS_API_URL}/generate", params={"param": "anything-not-sv"})
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["created_count"] == 2
        assert set(body["created_names"]) == {"Stars", "Transients"}

        assert uow.panels.add.call_count == 2
        created_names = [call.args[0].name for call in uow.panels.add.call_args_list]
        assert set(created_names) == {"Stars", "Transients"}
        uow.commit.assert_called_once()

    # Category: All exist -> no creation, no commit
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    def test_generate_categories_all_exist_noop(
        self, mock_get_latest, mock_uow, client, monkeypatch
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        monkeypatch.setattr(panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True)

        mock_get_latest.side_effect = [
            [SimpleNamespace(panel_id="panel-cosmology")],
            [SimpleNamespace(panel_id="panel-stars")],
        ]

        resp = client.post(f"{PANELS_API_URL}/generate", params={"param": "galaxy"})
        assert resp.status_code == HTTPStatus.OK, resp.content

        body = resp.json()
        assert body["created_count"] == 0
        assert body["created_names"] == []

        uow.panels.add.assert_not_called()
        uow.commit.assert_not_called()

    # SV: Case-insensitive + trim
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    def test_generate_sv_case_insensitive_and_trim(self, mock_get_latest, mock_uow, client):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        mock_get_latest.return_value = []  # SV doesn't exist
        uow.panels.add.return_value = SimpleNamespace(
            panel_id="panel-sv-new", name="Science Verification"
        )

        resp = client.post(
            f"{PANELS_API_URL}/generate", params={"param": "   ScIeNcE VeRiFiCaTiOn   "}
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json() == "panel-sv-new"

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()


class TestPanelsAssignmentsAPI:
    # --------------------------------------------------------------------
    # SV: existing SV panel & NO submitted proposals--> return panel_id (str)
    # --------------------------------------------------------------------
    @mock.patch("ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_sv_no_submitted_returns_id_no_writes(
        self, mock_uow, mock_get_latest, mock_build_sv, mock_ensure, client
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        # get_latest calls:
        # 1) submitted proposals
        # 2) existing SV panel lookup
        mock_get_latest.side_effect = [
            [],  # no submitted proposals
            [SimpleNamespace(panel_id="panel-sv", sci_reviewers=[], tech_reviewers=[])],
        ]

        resp = client.post(
            f"{PANELS_API_URL}/assignments", params={"param": "Science Verification"}
        )
        assert resp.status_code == HTTPStatus.OK, resp.text
        assert resp.json() == "panel-sv"

        # No commits, no status updates
        uow.panels.add.assert_not_called()
        uow.commit.assert_not_called()
        mock_build_sv.assert_not_called()
        mock_ensure.assert_not_called()

    # --------------------------------------------------------------------
    # SV: existing panel & submitted proposals--> append only NEW
    # -------------------------------------------------------------------
    @mock.patch("ska_oso_services.pht.api.panels.ensure_review_exist_or_create")
    @mock.patch("ska_oso_services.pht.api.panels.ensure_decision_exist_or_create")
    @mock.patch("ska_oso_services.pht.api.panels.build_assignment_response")
    @mock.patch("ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review")
    @mock.patch("ska_oso_services.pht.api.panels.build_sv_panel_proposals")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_sv_with_submitted_adds_only_new_and_returns_summary(
        self,
        mock_uow,
        mock_get_latest,
        mock_build_sv,
        mock_ensure_status,
        mock_build_resp,
        mock_ensure_decision,
        mock_ensure_review,
        client,
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        # Two submitted proposals
        proposal1 = SimpleNamespace(prsl_id="p1")
        proposal2 = SimpleNamespace(prsl_id="p2")
        submitted_refs = [proposal1, proposal2]

        mock_get_latest.side_effect = [
            submitted_refs,
            [SimpleNamespace(panel_id="panel-sv")],
        ]

        reviewer_id = REVIEWERS["sci_reviewers"][0]["id"]

        sv_panel = TestDataFactory.panel_with_assignment(
            panel_id="panel-sv",
            name="Science Verification",
            sci_reviewers=[
                {
                    "reviewer_id": reviewer_id,
                    "assigned_on": "2025-06-16T11:23:01Z",
                    "status": "Pending",
                }
            ],
            tech_reviewers=[
                {
                    "reviewer_id": reviewer_id,
                    "assigned_on": "2025-06-16T11:23:01Z",
                    "status": "Pending",
                }
            ],
            proposals=[
                {"prsl_id": proposal1.prsl_id, "assigned_on": "2025-05-21T09:30:00Z"},
                {"prsl_id": proposal2.prsl_id, "assigned_on": "2025-05-21T09:45:00Z"},
            ],
            cycle="test",
            expiry_date="2025-12-31T00:00:00Z",
        )

        # sv_panel.proposals contains two ProposalAssignment models
        assignment1, assignment2 = sv_panel.proposals

        # Only p1 is assigned
        sv_panel.proposals = [assignment1]
        uow.panels.get.return_value = sv_panel

        # SV candidates include both p1 and p2
        mock_build_sv.return_value = [assignment1, assignment2]

        # Decision/review creation
        mock_ensure_decision.return_value = "pnld-1"
        mock_ensure_review.return_value = "rvw-1"

        # Returns the panel object
        uow.panels.add.return_value = sv_panel

        mock_build_resp.return_value = [
            {
                "panel_id": "panel-sv",
                "name": "Science Verification",
                "proposals_added": 1,
                "total_proposals_after": 2,
            }
        ]

        resp = client.post(
            f"{PANELS_API_URL}/assignments",
            params={"param": "Science Verification"},
        )

        assert resp.status_code == HTTPStatus.OK, resp.text
        assert resp.json() == mock_build_resp.return_value

        uow.panels.add.assert_called_once()
        uow.commit.assert_called_once()

        assert mock_ensure_status.call_count == 1
        args, _ = mock_ensure_status.call_args
        ids_iter = args[2]
        assert set(list(ids_iter)) == {"p2"}

        mock_build_resp.assert_called_once()
        passed_map = mock_build_resp.call_args[0][0]
        assert set(passed_map.keys()) == {panels_api.SV_NAME}
        persisted, added_cnt = passed_map[panels_api.SV_NAME]
        assert added_cnt == 1
        assert persisted is sv_panel

    @mock.patch("ska_oso_services.pht.api.panels.build_assignment_response")
    @mock.patch("ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review")
    @mock.patch("ska_oso_services.pht.api.panels.assign_to_existing_panel")
    @mock.patch("ska_oso_services.pht.api.panels.group_proposals_by_science_category")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_category_assigns_skips_missing_and_updates_status(
        self,
        mock_uow,
        mock_get_latest,
        mock_group,
        mock_assign,
        mock_ensure,
        mock_build_resp,
        client,
        monkeypatch,
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        # deterministic pool
        monkeypatch.setattr(panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True)

        # get_latest call sequence (exactly 3 calls):
        # 1) fetch SUBMITTED proposals
        # 2) lookup "Cosmology" panel
        # 3) lookup "Stars" panel
        mock_get_latest.side_effect = [
            [SimpleNamespace(prsl_id="c1"), SimpleNamespace(prsl_id="s1")],  # SUBMITTED
            [SimpleNamespace(panel_id="panel-cosmo")],  # Cosmology exists
            [],  # Stars missing
        ]

        mock_group.return_value = {
            "Cosmology": [SimpleNamespace(prsl_id="c1")],
            "Stars": [SimpleNamespace(prsl_id="s1")],
        }

        cosmo_panel = SimpleNamespace(
            panel_id="panel-cosmo",
            name="Cosmology",
            proposals=[],
            sci_reviewers=["keep-sci"],
            tech_reviewers=["keep-tech"],
        )
        uow.panels.get.return_value = cosmo_panel

        mock_assign.return_value = (cosmo_panel, 1, ["c1"])

        mock_build_resp.return_value = [
            {
                "panel_id": "panel-cosmo",
                "name": "Cosmology",
                "proposals_added": 1,
                "total_proposals_after": 1,
            }
        ]

        resp = client.post(f"{PANELS_API_URL}/assignments", params={"param": "not-sv"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == mock_build_resp.return_value

        # commits once before status update
        uow.commit.assert_called_once()

        args, _ = mock_ensure.call_args
        ids_passed = set(args[2]) if not isinstance(args[2], set) else args[2]
        assert ids_passed == {"c1"}

        # assign_to_existing_panel called once
        mock_assign.assert_called_once()
        kwargs = mock_assign.call_args.kwargs
        assert kwargs["panel"] is cosmo_panel
        assert [p.prsl_id for p in kwargs["proposals"]] == ["c1"]
        assert kwargs["sci_reviewers"] == cosmo_panel.sci_reviewers
        assert kwargs["tech_reviewers"] == cosmo_panel.tech_reviewers

        mock_build_resp.assert_called_once()
        updates = mock_build_resp.call_args[0][0]
        assert set(updates.keys()) == {"Cosmology"}

    # --------------------------------------------------------------------
    # Category: no existing panels (all missing) --> empty list, no status
    # --------------------------------------------------------------------
    @mock.patch("ska_oso_services.pht.api.panels.build_assignment_response")
    @mock.patch("ska_oso_services.pht.api.panels.ensure_submitted_proposals_under_review")
    @mock.patch("ska_oso_services.pht.api.panels.group_proposals_by_science_category")
    @mock.patch("ska_oso_services.pht.api.panels.get_latest_entity_by_id")
    @mock.patch("ska_oso_services.pht.api.panels.oda.uow")
    def test_category_all_missing_returns_empty_and_no_status_update(
        self,
        mock_uow,
        mock_get_latest,
        mock_group,
        mock_ensure,
        mock_build_resp,
        client,
        monkeypatch,
    ):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        monkeypatch.setattr(panels_api, "PANEL_NAME_POOL", ["Cosmology", "Stars"], raising=True)

        mock_get_latest.side_effect = [
            [SimpleNamespace(prsl_id="c1"), SimpleNamespace(prsl_id="s1")],  # SUBMITTED
            [],  # Cosmology missing
            [],  # Stars missing
        ]

        mock_group.return_value = {
            "Cosmology": [SimpleNamespace(prsl_id="c1")],
            "Stars": [SimpleNamespace(prsl_id="s1")],
        }

        # No updates --> build empty response
        mock_build_resp.return_value = []

        resp = client.post(f"{PANELS_API_URL}/assignments", params={"param": "anything"})
        assert resp.status_code == HTTPStatus.OK, resp.text
        assert resp.json() == []

        uow.commit.assert_called_once()
        mock_ensure.assert_not_called()
        mock_build_resp.assert_called_once()
        assert mock_build_resp.call_args[0][0] == {}
