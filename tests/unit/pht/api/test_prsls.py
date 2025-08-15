"""
Unit tests for ska_oso_pht_services.api
"""

from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

import pytest
from aiosmtplib.errors import SMTPConnectError, SMTPException, SMTPRecipientsRefused
from fastapi import status
from ska_db_oda.persistence.domain.query import CustomQuery

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

    @pytest.mark.parametrize(
        "proposal_status,permissions",
        [
            ("submitted", ["submit", "view"]),
            ("submitted", ["submit"]),
            ("draft", ["update", "view"]),
            ("draft", ["update"]),
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.api.prsls."
        "assert_user_has_permission_for_proposal_return_rows",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_success(
        self, mock_uow, mock_acl, proposal_status, permissions, client
    ):
        """
        Check the prsls_put method returns the expected response
        """

        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True

        if proposal_status == "submitted":
            proposal_obj = TestDataFactory.complete_proposal()
        else:
            proposal_obj = TestDataFactory.proposal()

        proposal_obj.status = proposal_status
        proposal_id = proposal_obj.prsl_id
        uow_mock.prsls.add.return_value = proposal_obj
        uow_mock.prsls.get.return_value = proposal_obj
        mock_uow().__enter__.return_value = uow_mock

        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=permissions)
        ]

        result = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, proposal_obj.model_dump_json())

    @pytest.mark.parametrize(
        "proposal_status,permissions",
        [
            ("submitted", ["view", "update"]),
            ("submitted", []),
            ("draft", ["view"]),
            ("draft", []),
        ],
    )
    @mock.patch(
        "ska_oso_services.pht.api.prsls."
        "assert_user_has_permission_for_proposal_return_rows",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_forbidden(
        self, mock_uow, mock_acl, proposal_status, permissions, client
    ):
        """
        Check the prsls_put method returns forbidden when the user has no permission
        """

        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True

        if proposal_status == "submitted":
            proposal_obj = TestDataFactory.complete_proposal()
        else:
            proposal_obj = TestDataFactory.proposal()

        proposal_obj.status = proposal_status
        proposal_id = proposal_obj.prsl_id
        uow_mock.prsls.add.return_value = proposal_obj
        uow_mock.prsls.get.return_value = proposal_obj
        mock_uow().__enter__.return_value = uow_mock

        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=permissions)
        ]

        result = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "proposal_status,permissions",
        [
            ("submitted", ["view", "update"]),
        ],
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_proposal_put_forbidden_without_mock_proposal_service(
        self, mock_uow, proposal_status, permissions, client
    ):
        """
        Check the prsls_put method returns forbidden when the user has no permission
        """

        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True

        proposal_obj = TestDataFactory.complete_proposal()

        proposal_obj.status = proposal_status
        proposal_id = proposal_obj.prsl_id
        uow_mock.prsls.add.return_value = proposal_obj
        uow_mock.prsls.get.return_value = proposal_obj
        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.FORBIDDEN

    @mock.patch(
        "ska_oso_services.pht.api.prsls."
        "assert_user_has_permission_for_proposal_return_rows",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_not_found(self, mock_uow, mock_acl, client):
        """
        Should return 404 if proposal doesn't exist.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["update"])
        ]

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch(
        "ska_oso_services.pht.api.prsls."
        "assert_user_has_permission_for_proposal_return_rows",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_id_mismatch(self, mock_uow, mock_acl, client):
        """
        Should raise 422 when ID in path != payload.
        """
        proposal_obj = TestDataFactory.proposal()
        path_id = "diff-id"

        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["update"])
        ]

        response = client.put(
            f"{PROPOSAL_API_URL}/{path_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in response.json()["detail"].lower()

    @mock.patch(
        "ska_oso_services.pht.api.prsls."
        "assert_user_has_permission_for_proposal_return_rows",
        autospec=True,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_update_proposal_validation_error(self, mock_oda, mock_acl, client):
        """
        Should return 400 if .add() raises ValueError.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal_obj
        uow_mock.prsls.add.side_effect = ValueError("Invalid proposal content")
        mock_oda.return_value.__enter__.return_value = uow_mock

        mock_acl.return_value = [
            TestDataFactory.proposal_access(permissions=["update"])
        ]

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "validation error" in response.json()["detail"].lower()

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
        res = response.json()
        assert res == []

    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow")
    def test_get_reviews_for_panel_with_valid_id(self, mock_oda, client):
        """
        Test reviews for a proposal with a valid ID returns the expected reviews.
        """
        review_objs = [
            TestDataFactory.reviews(prsl_id="my proposal"),
        ]
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = review_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        prsl_id = "my proposal"
        response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")
        assert response.status_code == HTTPStatus.OK

        expected = [
            obj.model_dump(mode="json", exclude={"metadata"}) for obj in review_objs
        ]
        response = response.json()
        del response[0]["metadata"]
        assert expected == response
        assert response[0]["review_id"] == expected[0]["review_id"]
        assert response[0]["panel_id"] == expected[0]["panel_id"]


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
