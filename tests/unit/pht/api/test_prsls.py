"""
Unit tests for ska_oso_pht_services.api
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

import pytest
from aiosmtplib.errors import SMTPConnectError, SMTPException, SMTPRecipientsRefused
from fastapi import status
from pydantic import BaseModel, ValidationError
from ska_db_oda.persistence.domain.query import CustomQuery

from ska_oso_services.common.error_handling import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from ska_oso_services.pht.api.prsls import get_proposals_by_status
from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import (
    PAYLOAD_BAD_TO,
    PAYLOAD_CONNECT_FAIL,
    PAYLOAD_GENERIC_FAIL,
    PAYLOAD_SUCCESS,
    VALID_NEW_PROPOSAL,
    TestDataFactory,
    assert_json_is_equal,
)

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/prsls"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


from ska_oso_services.pht.service import proposal_service as ps

MODULE = "ska_oso_services.pht.service.proposal_service"


class TestListAccess:
    @mock.patch(f"{MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{MODULE}.CustomQuery", autospec=True)
    def test_list_ids_happy_path(self, mock_cq, mock_latest):
        user_id = "user-123"
        q = object()
        mock_cq.return_value = q

        uow = mock.MagicMock()
        rows_init = [object()]
        uow.prslacc.query.return_value = rows_init

        mock_latest.return_value = [
            SimpleNamespace(access_id="a2", prsl_id="prsl-b"),
            SimpleNamespace(access_id="a1", prsl_id="prsl-a"),
            SimpleNamespace(access_id="a3", prsl_id="prsl-a"),
        ]

        got = ps.list_accessible_proposal_ids(uow, user_id)

        assert got == ["prsl-a", "prsl-b"]
        mock_cq.assert_called_once_with(user_id=user_id)
        uow.prslacc.query.assert_called_once_with(q)
        mock_latest.assert_called_once_with(rows_init, "access_id")

    @mock.patch(f"{MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{MODULE}.CustomQuery", autospec=True)
    def test_list_ids_none_paths(self, mock_cq, mock_latest):
        uow = mock.MagicMock()
        uow.prslacc.query.return_value = None
        mock_latest.return_value = None

        got = ps.list_accessible_proposal_ids(uow, "u")

        assert got == []
        mock_latest.assert_called_once_with([], "access_id")


class TestProposalAPI:
    @mock.patch("ska_oso_services.pht.api.prsls.get_osd_data")
    def test_get_osd_data_fail(self, mock_get_osd, client):
        mock_get_osd.return_value = ({"detail": "some error"}, None)
        cycle = "-1"
        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/{cycle}")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        res = response.json()
        assert {"detail": "some error"} == res

    @mock.patch("ska_oso_services.pht.api.prsls.get_osd_data")
    def test_get_osd_data_success(self, mock_get_osd, client):
        expected = {
            "observatory_policy": {
                "cycle_number": 1,
                "cycle_description": "Science Verification",
                "cycle_information": {
                    "cycle_id": "SKAO_2027_1",
                    "proposal_open": "20260327T12:00:00.000Z",
                    "proposal_close": "20260512T15:00:00.000z",
                },
                "cycle_policies": {"normal_max_hours": 100.0},
                "telescope_capabilities": {"Mid": "AA2", "Low": "AA2"},
            },
            "capabilities": {
                "mid": {
                    "basic_capabilities": {
                        "dish_elevation_limit_deg": 15.0,
                        "receiver_information": [
                            {
                                "rx_id": "Band_1",
                                "min_frequency_hz": 350000000.0,
                                "max_frequency_hz": 1050000000.0,
                            },
                            {
                                "rx_id": "Band_2",
                                "min_frequency_hz": 950000000.0,
                                "max_frequency_hz": 1760000000.0,
                            },
                            {
                                "rx_id": "Band_3",
                                "min_frequency_hz": 1650000000.0,
                                "max_frequency_hz": 3050000000.0,
                            },
                            {
                                "rx_id": "Band_4",
                                "min_frequency_hz": 2800000000.0,
                                "max_frequency_hz": 5180000000.0,
                            },
                            {
                                "rx_id": "Band_5a",
                                "min_frequency_hz": 4600000000.0,
                                "max_frequency_hz": 8500000000.0,
                            },
                            {
                                "rx_id": "Band_5b",
                                "min_frequency_hz": 8300000000.0,
                                "max_frequency_hz": 15400000000.0,
                            },
                        ],
                    },
                    "AA2": {
                        "available_receivers": [
                            "Band_1",
                            "Band_2",
                            "Band_5a",
                            "Band_5b",
                        ],
                        "number_ska_dishes": 64,
                        "number_meerkat_dishes": 4,
                        "number_meerkatplus_dishes": 0,
                        "max_baseline_km": 110.0,
                        "available_bandwidth_hz": 800000000.0,
                        "number_channels": 14880,
                        "cbf_modes": ["CORR", "PST_BF", "PSS_BF"],
                        "number_zoom_windows": 16,
                        "number_zoom_channels": 14880,
                        "number_pss_beams": 384,
                        "number_pst_beams": 6,
                        "ps_beam_bandwidth_hz": 800000000.0,
                        "number_fsps": 4,
                    },
                },
                "low": {
                    "basic_capabilities": {
                        "min_frequency_hz": 50000000.0,
                        "max_frequency_hz": 350000000.0,
                    },
                    "AA2": {
                        "number_stations": 64,
                        "number_substations": 720,
                        "number_beams": 8,
                        "max_baseline_km": 40.0,
                        "available_bandwidth_hz": 150000000.0,
                        "channel_width_hz": 5400,
                        "cbf_modes": ["vis", "pst", "pss"],
                        "number_zoom_windows": 16,
                        "number_zoom_channels": 1800,
                        "number_pss_beams": 30,
                        "number_pst_beams": 4,
                        "number_vlbi_beams": 0,
                        "ps_beam_bandwidth_hz": 118000000.0,
                        "number_fsps": 10,
                    },
                },
            },
        }

        mock_get_osd.return_value = expected
        cycle = 1
        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/{cycle}")

        assert response.status_code == HTTPStatus.OK
        res = response.json()
        assert expected == res

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_create_proposal(self, mock_oda, client):
        """
        Check the proposal_create method returns the expected prsl_id and status code.
        """

        proposal_obj = TestDataFactory.proposal()

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.return_value = proposal_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=VALID_NEW_PROPOSAL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == proposal_obj.prsl_id

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_create_proposal_value_error_raises_bad_request(self, mock_oda, client):
        """
        Simulate ValueError in proposal creation and ensure it raises BadRequestError.
        """

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.side_effect = ValueError("mock-failure")

        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=VALID_NEW_PROPOSAL,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a proposal" in data["detail"]

    @mock.patch(
        f"{MODULE}.assert_user_has_permission_for_proposal",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_not_found(self, mock_oda, mock_acl, client):
        """
        Ensure KeyError during get() raises NotFoundError.
        """
        proposal_id = "prsl-missing-9999"

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = KeyError(proposal_id)
        uow_mock.prslacc.query.return_value = [
            {"access_id": "acc-1", "prsl_id": proposal_id, "user_id": "user-123"}
        ]

        mock_oda.return_value.__enter__.return_value = uow_mock
        mock_oda.return_value.__exit__.return_value = None

        mock_acl.return_value = None

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Could not find proposal" in response.json()["detail"]

    @mock.patch(
        f"{MODULE}.assert_user_has_permission_for_proposal",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_success(self, mock_oda, mock_acl, client):
        """
        Ensure valid proposal ID returns the Proposal object.
        """
        proposal = TestDataFactory.proposal()
        proposal_id = proposal.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal
        uow_mock.prslacc.query.return_value = [
            {"access_id": "acc-1", "prsl_id": proposal_id, "user_id": "user-123"}
        ]

        mock_oda.return_value.__enter__.return_value = uow_mock
        mock_oda.return_value.__exit__.return_value = None

        mock_acl.return_value = None

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["prsl_id"] == proposal_id
        assert data["info"]["title"] == proposal.info.title

    @mock.patch(
        "ska_oso_services.pht.api.prsls.list_accessible_proposal_ids", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_list_success(self, mock_uow, mock_list_ids, client_get):
        # Arrange
        proposal_objs = [TestDataFactory.proposal(), TestDataFactory.proposal()]
        proposal_ids = [p.prsl_id for p in proposal_objs]
        mock_list_ids.return_value = proposal_ids

        uow = mock.MagicMock()
        uow.prsls.get.side_effect = lambda pid: next(
            (p for p in proposal_objs if p.prsl_id == pid), None
        )

        mock_uow.return_value.__enter__.return_value = uow
        mock_uow.return_value.__exit__.return_value = None

        # Act
        resp = client_get(f"{PROPOSAL_API_URL}/mine")

        # Assert
        assert resp.status_code == HTTPStatus.OK, resp.json()
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == len(proposal_objs)
        mock_list_ids.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.api.prsls.list_accessible_proposal_ids", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposal_list_empty(self, mock_uow, mock_list_ids, client_get):
        mock_list_ids.return_value = []

        mock_uow.return_value.__enter__.return_value = mock.MagicMock()
        mock_uow.return_value.__exit__.return_value = None

        resp = client_get(f"{PROPOSAL_API_URL}/mine")
        assert resp.status_code == HTTPStatus.OK, resp.json()
        assert resp.json() == []

    @mock.patch(
        "ska_oso_services.pht.api.prsls.update_proposal_with_assignment", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_commit_valueerror_does_not_double_persist(
        self, mock_uow, mock_update_service, client
    ):
        """
        Sanity: on commit failure, we don't try multiple commits / extra writes.
        """
        body = TestDataFactory.proposal()
        prsl_id = body.prsl_id
        mock_update_service.return_value = body

        uow_ctx = mock.MagicMock()
        mock_uow().__enter__.return_value = uow_ctx
        uow_ctx.commit.side_effect = ValueError("db-commit-boom")

        resp = client.put(
            f"{PROPOSAL_API_URL}/{prsl_id}",
            data=body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert uow_ctx.commit.call_count == 1

        uow_ctx.prsls.add.assert_not_called()


class TestGetProposalReview:
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_reviews_for_proposal_with_wrong_id(self, mock_oda, client):
        """
        Test reviews for a proposal with a wrong ID returns an empty list.
        """
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = []
        mock_oda.return_value.__enter__.return_value = uow_mock

        prsl_id = "wrong id"
        response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow")
    def test_get_reviews_for_panel_with_valid_id(self, mock_oda, client):
        """
        Test reviews for a proposal with a valid ID returns the expected reviews.
        """
        review_objs = [TestDataFactory.reviews(prsl_id="my proposal")]
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = review_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        prsl_id = "my proposal"
        response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")
        assert response.status_code == HTTPStatus.OK

        expected = [
            obj.model_dump(mode="json", exclude={"metadata"}) for obj in review_objs
        ]
        payload = response.json()
        # align shapes by dropping metadata
        del payload[0]["metadata"]
        assert expected == payload
        assert payload[0]["review_id"] == expected[0]["review_id"]
        assert payload[0]["panel_id"] == expected[0]["panel_id"]


class TestUpdateProposalWithAssignmentEarlyPaths:
    @staticmethod
    def _iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # -------Validation error (transform or model_validate) -> 400 ----------
    @pytest.mark.parametrize("raise_at", ["transform", "model_validate"])
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.ValidationError", new=Exception
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.transform_update_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.Proposal.model_validate",
        autospec=True,
    )
    def test_validation_error_paths_raise_400(
        self, mock_model_validate, mock_transform, raise_at
    ):
        user_id = "user-123"
        uow = mock.MagicMock()
        payload = TestDataFactory.proposal()

        uow.prsls.get.return_value = TestDataFactory.proposal()

        if raise_at == "transform":
            mock_transform.side_effect = Exception(
                "transform_update_proposal validation failure"
            )
        else:
            mock_transform.return_value = payload.model_dump(mode="json")
            mock_model_validate.side_effect = Exception(
                "Proposal.model_validate validation failure"
            )

        with pytest.raises(BadRequestError):
            ps.update_proposal_with_assignment(
                uow=uow, prsl_id="prsl-1", payload=payload, user_id=user_id
            )

        uow.prsls.add.assert_not_called()
        uow.panels.add.assert_not_called()

    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.transform_update_proposal",
        autospec=True,
    )
    def test_existing_proposal_not_found_raises_404(self, mock_transform):
        user_id = "user-123"
        uow = mock.MagicMock()

        payload = TestDataFactory.proposal()
        mock_transform.return_value = payload.model_dump(mode="json")
        uow.prsls.get.return_value = None

        with pytest.raises(NotFoundError):
            ps.update_proposal_with_assignment(
                uow=uow, prsl_id="missing-1", payload=payload, user_id=user_id
            )

    @pytest.mark.parametrize(
        "status,required_perm", [("draft", "update"), ("submitted", "submit")]
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service." "transform_update_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service"
        ".assert_user_has_permission_for_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service." "proposal_service.get_latest_entity_by_id",
        autospec=True,
    )
    def test_permissions_invocation(
        self, mock_get_latest, mock_acl, mock_transform, status, required_perm
    ):
        user_id = "user-123"
        uow = mock.MagicMock()

        payload = (
            TestDataFactory.complete_proposal()
            if status == "submitted"
            else TestDataFactory.proposal()
        )
        payload.status = status
        if status == "submitted":
            payload.submitted_on = "2025-06-01T00:00:00Z"

        mock_transform.return_value = payload.model_dump(mode="json")
        uow.prsls.get.return_value = TestDataFactory.proposal()
        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=[required_perm])
        ]

        if status == "submitted":
            mock_get_latest.side_effect = [
                [],  # no SV panel
                [SimpleNamespace(panel_id="panel-cat", proposals=[])],
            ]
            uow.prsls.add.side_effect = lambda c, uid: c

        ps.update_proposal_with_assignment(
            uow=uow, prsl_id=payload.prsl_id, payload=payload, user_id=user_id
        )

        mock_acl.assert_called_once()
        _, kwargs = mock_acl.call_args
        assert kwargs["uow"] is uow
        assert kwargs["prsl_id"] == payload.prsl_id
        assert kwargs["user_id"] == user_id

    @pytest.mark.parametrize(
        "submitted_on_value",
        [
            "2025-06-01T00:00:00Z",  # ISO Z string
            datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc),  # tz-aware datetime
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service." "transform_update_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service"
        ".assert_user_has_permission_for_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service." "proposal_service.get_latest_entity_by_id",
        autospec=True,
    )
    def test_as_utc_dt_inputs_flow_to_assignment_valid(
        self, mock_get_latest, mock_acl, mock_transform, submitted_on_value
    ):
        user_id = "user-123"
        uow = mock.MagicMock()

        # Build a valid submitted body that the service will model_validate
        payload = TestDataFactory.complete_proposal()
        body = payload.model_dump(mode="json")
        body["status"] = "submitted"
        body["submitted_on"] = submitted_on_value
        mock_transform.return_value = body

        # Proposal exists
        uow.prsls.get.return_value = TestDataFactory.proposal()
        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["submit"])
        ]

        # No SV panel; category panel exists
        panel = SimpleNamespace(panel_id="panel-cosmos", proposals=[])
        mock_get_latest.side_effect = [
            [],  # SV panel lookup
            [panel],  # category panel lookup
        ]

        # Echo the candidate from repo.add
        uow.prsls.add.side_effect = lambda c, uid: c

        out = ps.update_proposal_with_assignment(
            uow=uow, prsl_id=payload.prsl_id, payload=payload, user_id=user_id
        )

        # We don't check the exact timestamp; just that
        # assignment happened and status persisted
        uow.panels.add.assert_called_once()
        saved_panel = uow.panels.add.call_args[0][0]
        assert saved_panel is panel
        assert any(
            getattr(a, "prsl_id", None) == payload.prsl_id for a in panel.proposals
        )
        assert str(out.status).lower().endswith("under review")
        uow.prsls.add.assert_called_once()

    # ---- Naive datetime should be rejected by the model -> 400 ----
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.transform_update_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service."
        "assert_user_has_permission_for_proposal",
        autospec=True,
    )
    def test_naive_submitted_on_rejected_with_400(self, mock_acl, mock_transform):
        user_id = "user-123"
        uow = mock.MagicMock()

        payload = TestDataFactory.complete_proposal()

        # Return a body dict with a NAIVE datetime for submitted_on
        naive_dt = datetime(2025, 6, 1, 0, 0, 0)  # no tzinfo
        body = payload.model_dump(mode="json")
        body["status"] = "submitted"
        body["submitted_on"] = naive_dt
        mock_transform.return_value = body

        # Ensure we get past the 'existing' check and perms
        uow.prsls.get.return_value = TestDataFactory.proposal()
        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["submit"])
        ]

        with pytest.raises(BadRequestError):
            ps.update_proposal_with_assignment(
                uow=uow, prsl_id=payload.prsl_id, payload=payload, user_id=user_id
            )

        # Nothing persisted on validation failure
        uow.panels.add.assert_not_called()
        uow.prsls.add.assert_not_called()

    # ----Unsupported but valid enum (neither DRAFT nor SUBMITTED) -> 400 ----
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.transform_update_proposal",
        autospec=True,
    )
    def test_status_neither_draft_nor_submitted_raises_400(self, mock_transform):
        user_id = "user-123"
        uow = mock.MagicMock()

        payload = TestDataFactory.complete_proposal()
        body = payload.model_dump(mode="json")

        # Use a VALID enum that is neither DRAFT nor SUBMITTED so model_validate passes
        body["status"] = ps.ProposalStatus.UNDER_REVIEW
        mock_transform.return_value = body

        # Existing proposal check passes
        uow.prsls.get.return_value = TestDataFactory.complete_proposal()

        with pytest.raises(BadRequestError):
            ps.update_proposal_with_assignment(
                uow=uow, prsl_id=payload.prsl_id, payload=payload, user_id=user_id
            )

        uow.prsls.add.assert_not_called()
        uow.panels.add.assert_not_called()

    @pytest.mark.parametrize(
        "submitted_on_value",
        [
            "2025-12-31T00:00:00Z",  # exactly at CLOSE_ON
            "2026-01-01T00:00:00Z",  # after CLOSE_ON
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service." "transform_update_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service"
        ".assert_user_has_permission_for_proposal",
        autospec=True,
    )
    @mock.patch(
        "ska_oso_services.pht.service.proposal_service.get_latest_entity_by_id",
        autospec=True,
    )
    def test_close_gate_submitted_on_at_or_after_close_skips_assignment(
        self, mock_get_latest, mock_acl, mock_transform, submitted_on_value
    ):
        """
        If submitted_on is at/after CLOSE_ON, service must:
        - return existing proposal,
        - NOT assign to any panel,
        - NOT persist any changes,
        - NOT even look up panels.
        """
        user_id = "user-123"
        uow = mock.MagicMock()

        payload = TestDataFactory.complete_proposal()
        body = payload.model_dump(mode="json")
        body["status"] = "submitted"
        body["submitted_on"] = submitted_on_value
        mock_transform.return_value = body

        # Existing proposal with same id so service can return it unchanged
        existing = TestDataFactory.complete_proposal(prsl_id=payload.prsl_id)
        uow.prsls.get.return_value = existing

        # Have submit permission so we reach the close-date gate
        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["submit"])
        ]

        out = ps.update_proposal_with_assignment(
            uow=uow, prsl_id=payload.prsl_id, payload=payload, user_id=user_id
        )

        # Returned object is exactly the existing proposal (no mutation/persist)
        assert out is existing

        # No repo writes, no panel lookups/updates
        uow.prsls.add.assert_not_called()
        uow.panels.add.assert_not_called()
        mock_get_latest.assert_not_called()


class TestPutProposalAPI:
    @mock.patch(
        "ska_oso_services.pht.api.prsls.update_proposal_with_assignment", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_id_mismatch_returns_422(
        self, mock_uow, mock_update_service, client
    ):
        body = TestDataFactory.proposal()
        path_id = f"{body.prsl_id}-DIFF"

        resp = client.put(
            f"{PROPOSAL_API_URL}/{path_id}",
            data=body.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in resp.text.lower()

        mock_update_service.assert_not_called()
        mock_uow().__enter__.assert_not_called()

    @pytest.mark.parametrize(
        "initial_status,final_status",
        [
            ("draft", "draft"),
            ("submitted", "under review"),
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.api.prsls.update_proposal_with_assignment", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_success(
        self, mock_uow, mock_update_service, initial_status, final_status, client
    ):
        incoming = TestDataFactory.complete_proposal()
        incoming.status = initial_status
        proposal_id = incoming.prsl_id

        returned = TestDataFactory.complete_proposal(prsl_id=proposal_id)
        returned.status = final_status
        mock_update_service.return_value = returned

        uow_mock = mock.MagicMock()
        mock_uow().__enter__.return_value = uow_mock

        resp = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=incoming.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == returned.model_dump(mode="json")

        assert mock_update_service.call_count == 1
        _, kwargs = mock_update_service.call_args
        assert kwargs["prsl_id"] == proposal_id
        assert kwargs["uow"] is uow_mock
        assert "user_id" in kwargs

        uow_mock.commit.assert_called_once()

    @pytest.mark.parametrize(
        "exc_cls,http_code",
        [
            (ForbiddenError, HTTPStatus.FORBIDDEN),
            (NotFoundError, HTTPStatus.NOT_FOUND),
            (BadRequestError, HTTPStatus.BAD_REQUEST),
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.api.prsls.update_proposal_with_assignment", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_error_paths(
        self, mock_uow, mock_update_service, exc_cls, http_code, client
    ):
        incoming = TestDataFactory.proposal()
        proposal_id = incoming.prsl_id

        # Clearer message than "boom"
        mock_update_service.side_effect = exc_cls("simulated service failure")

        uow_mock = mock.MagicMock()
        mock_uow().__enter__.return_value = uow_mock

        resp = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=incoming.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == http_code
        uow_mock.commit.assert_not_called()

    @mock.patch(
        "ska_oso_services.pht.api.prsls.update_proposal_with_assignment", autospec=True
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_commit_value_error_returns_400(
        self, mock_uow, mock_update_service, client
    ):
        incoming = TestDataFactory.proposal()
        proposal_id = incoming.prsl_id

        updated = TestDataFactory.proposal(prsl_id=proposal_id)
        mock_update_service.return_value = updated

        uow_mock = mock.MagicMock()
        # Clearer message than "broken commit"
        uow_mock.commit.side_effect = ValueError("simulated database commit failure")
        mock_uow().__enter__.return_value = uow_mock

        resp = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=incoming.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST
        detail = resp.json().get("detail", "").lower()
        assert "validation error while saving proposal" in detail

        mock_update_service.assert_called_once()
        uow_mock.commit.assert_called_once()


class TestProposalBatch:
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposals_batch_all_found(self, mock_oda, client):
        proposal1 = TestDataFactory.proposal(prsl_id="prsl-ska-00001")
        proposal2 = TestDataFactory.proposal(prsl_id="prsl-ska-00002")
        prsl_map = {"prsl-ska-00001": proposal1, "prsl-ska-00002": proposal2}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = prsl_map.get
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/batch",
            json={"prsl_ids": ["prsl-ska-00001", "prsl-ska-00002"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert {obj["prsl_id"] for obj in data} == {"prsl-ska-00001", "prsl-ska-00002"}

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposals_batch_partial_found(self, mock_oda, client):
        proposal1 = TestDataFactory.proposal(prsl_id="prsl-ska-00001")
        prsl_map = {"prsl-ska-00001": proposal1}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = prsl_map.get
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/batch",
            json={"prsl_ids": ["prsl-ska-00001", "prsl-ska-00004"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["prsl_id"] == "prsl-ska-00001"

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_get_proposals_batch_none_found(self, mock_oda, client):
        """
        Test when proposal ids are not found
        """
        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = None
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/batch", json={"prsl_ids": ["PRSL999", "PRSL888"]}
        )
        assert response.status_code == 200
        assert response.json() == []


class TestProposalEmailAPI:
    @mock.patch("ska_oso_services.pht.api.prsls.send_email_async", autospec=True)
    def test_send_email_success(self, mock_send, client):
        """
        Check that a successful email send returns status 200 and success message.
        """
        mock_send.return_value = True

        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_SUCCESS,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Email sent successfully"}
        mock_send.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.email_service.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_connection_failure(self, mock_smtp_send, client):
        """
        Check that a SMTPConnectError returns status 503.
        """
        mock_smtp_send.side_effect = SMTPConnectError(b"Connection failed")
        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_CONNECT_FAIL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "SMTP connection failed" in response.text

    @mock.patch(
        "ska_oso_services.pht.service.email_service.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_recipients_refused(self, mock_smtp_send, client):
        """
        Check that SMTPRecipientsRefused returns status 400.
        """
        mock_smtp_send.side_effect = SMTPRecipientsRefused({})
        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_BAD_TO,
            headers={"Content-type": "application/json"},
        )

        assert "Unable to send email for this recipient." in response.text

    @mock.patch(
        "ska_oso_services.pht.service.email_service.aiosmtplib.send",
        new_callable=mock.AsyncMock,
    )
    def test_send_email_generic_smtp_exception(self, mock_smtp_send, client):
        """
        Check that generic SMTPException returns 502.
        """
        mock_smtp_send.side_effect = SMTPException("Some SMTP error")

        response = client.post(
            f"{PROPOSAL_API_URL}/send-email/",
            json=PAYLOAD_GENERIC_FAIL,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "SMTP send failed" in response.text


class TestGetProposalsByStatus:

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    @mock.patch("ska_oso_services.pht.api.prsls.get_latest_entity_by_id")
    def test_get_proposals_by_status_success(self, mock_get_latest, mock_uow):
        sample_proposal = TestDataFactory.complete_proposal(
            prsl_id="prsl-ska-00002", status="draft"
        )
        mock_query_result = [sample_proposal]

        uow_mock = mock.MagicMock()
        uow_mock.prsls.query.return_value = mock_query_result
        mock_uow.return_value.__enter__.return_value = uow_mock

        # Call returns raw proposal
        # Returns filtered/latest
        mock_get_latest.side_effect = [mock_query_result, mock_query_result]

        result = get_proposals_by_status("draft")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].prsl_id == "prsl-ska-00002"
        uow_mock.prsls.query.assert_called_once_with(CustomQuery(status="draft"))
        assert mock_get_latest.call_count == 2

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    @mock.patch("ska_oso_services.pht.api.prsls.get_latest_entity_by_id")
    def test_get_proposals_by_status_empty(self, mock_get_latest, mock_uow):
        empty_result = []

        uow_mock = mock.MagicMock()
        uow_mock.prsls.query.return_value = empty_result
        mock_uow.return_value.__enter__.return_value = uow_mock

        mock_get_latest.side_effect = [None]

        result = get_proposals_by_status("non-existent-status")

        assert result == []
        uow_mock.prsls.query.assert_called_once_with(
            CustomQuery(status="non-existent-status")
        )
        mock_get_latest.assert_called_once()
