"""
Unit tests for ska_oso_pht_services.api
"""

import copy
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

import pytest
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.api import prsls as prsl_api
from ska_oso_services.pht.api.prsls import get_proposals_by_status
from ska_oso_services.pht.service import proposal_service as ps
from ska_oso_services.pht.service.proposal_service import get_panel_prsl_ids
from ska_oso_services.pht.service.security.facts import Facts
from tests.conftest import PHT_BASE_API_URL
from tests.unit.util import (
    TestDataFactory,
    assert_json_is_equal,
)

PROPOSAL_API_URL = f"{PHT_BASE_API_URL}/prsls"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


MODULE = "ska_oso_services.pht.service.proposal_service"
PRSL_MODULE = "ska_oso_services.pht.api.prsls"


class TestOSD:
    mock_osd_data_cycle_1 = {
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
                    "allowed_channel_count_range_max": [1],
                    "allowed_channel_count_range_min": [2],
                    "allowed_channel_width_values": [3],
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
                    "available_bandwidth_hz": 800000000,
                    "number_channels": 14880,
                    "cbf_modes": ["correlation", "pst", "pss"],
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
    mock_osd_data_cycle_2 = copy.deepcopy(mock_osd_data_cycle_1)
    mock_osd_data_cycle_2["observatory_policy"]["cycle_number"] = 10000

    @mock.patch(f"{PRSL_MODULE}.get_osd_data")
    def test_get_osd_data_fail(self, mock_get_osd, client):
        mock_get_osd.return_value = ({"detail": "some error"}, None)
        cycle = "-1"
        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/{cycle}")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        res = response.json()
        assert {"detail": "some error"} == res

    @mock.patch(f"{PRSL_MODULE}.get_osd_data")
    def test_get_osd_data_success(self, mock_get_osd, client):
        expected = self.mock_osd_data_cycle_1
        mock_get_osd.return_value = expected
        cycle = 1
        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/{cycle}")

        assert response.status_code == HTTPStatus.OK
        res = response.json()
        assert res["observatory_policy"]["cycle_number"] == 1
        assert res["observatory_policy"]["cycle_information"]["cycle_id"] == "SKAO_2027_1"

    @mock.patch(f"{PRSL_MODULE}.get_osd_cycles")
    def test_get_osd_cycles_fail(self, mock_get_osd, client):
        mock_get_osd.return_value = ({"detail": "some error"}, None)
        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/cycles")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        res = response.json()
        assert {"detail": "some error"} == res

    @mock.patch(f"{PRSL_MODULE}.get_osd_data")
    @mock.patch(f"{PRSL_MODULE}.get_osd_cycles")
    def test_get_osd_cycles_success(self, mock_get_osd_cycles, mock_get_osd_data, client):
        mock_get_osd_cycles.return_value = {"cycles": [1, 10000]}

        mock_get_osd_data.side_effect = [
            self.mock_osd_data_cycle_1,
            self.mock_osd_data_cycle_2,
        ]

        response = client.get(f"{PHT_BASE_API_URL}/prsls/osd/cycles")

        assert response.status_code == HTTPStatus.OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["observatory_policy"]["cycle_number"] == 1
        assert data[1]["observatory_policy"]["cycle_number"] == 10000

        assert mock_get_osd_data.call_count == 2


class TestProposalAPI:
    @mock.patch(f"{PRSL_MODULE}.UserPortalService.create_membership", new_callable=mock.AsyncMock)
    @mock.patch(
        f"{PRSL_MODULE}.UserPortalService.create_proposal_groups",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
    def test_create_proposal(self, mock_oda, mock_create_groups, mock_create_membership, client):
        """
        Check the proposal_create method returns the expected prsl_id and status code.
        """

        proposal_obj = TestDataFactory.proposal()
        mock_create_groups.return_value = SimpleNamespace(admin="app:pht:prp-test/w/a")
        mock_create_membership.return_value = {}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.return_value = proposal_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=proposal_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json()["prsl_id"] == proposal_obj.prsl_id

    @mock.patch(f"{PRSL_MODULE}.UserPortalService.create_membership", new_callable=mock.AsyncMock)
    @mock.patch(
        f"{PRSL_MODULE}.UserPortalService.create_proposal_groups",
        new_callable=mock.AsyncMock,
    )
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_create_proposal_value_error_raises_bad_request(
        self, mock_oda, mock_create_groups, mock_create_membership, client
    ):
        """
        Simulate ValueError in proposal creation and ensure it raises BadRequestError.
        """

        mock_create_groups.return_value = SimpleNamespace(admin="app:pht:prp-test/w/a")
        mock_create_membership.return_value = {}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.add.side_effect = ValueError("mock-failure")

        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/create",
            data=TestDataFactory.proposal().model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a proposal" in data["detail"]

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposal_not_found(self, mock_oda, client):
        """
        Ensure KeyError during get() raises NotFoundError.
        """
        proposal_id = "prp-tm2ss2ng"

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = KeyError(proposal_id)
        uow_mock.prslacc.query.return_value = [
            TestDataFactory.proposal_access(
                access_id="acc-1", user_id="user-123", prsl_id=proposal_id
            )
        ]

        mock_oda.return_value.__enter__.return_value = uow_mock
        mock_oda.return_value.__exit__.return_value = None

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Could not find proposal" in response.json()["detail"]

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposal_success(self, mock_oda, client):
        """
        Ensure valid proposal ID returns the Proposal object.
        """
        proposal = TestDataFactory.proposal()
        proposal_id = proposal.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal
        uow_mock.prslacc.query.return_value = [
            TestDataFactory.proposal_access(
                access_id="acc-1", user_id="user-123", prsl_id=proposal_id
            )
        ]

        mock_oda.return_value.__enter__.return_value = uow_mock
        mock_oda.return_value.__exit__.return_value = None

        response = client.get(f"{PROPOSAL_API_URL}/{proposal_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["prsl_id"] == proposal_id
        assert data["proposal_info"]["title"] == proposal.proposal_info.title

    @mock.patch(
        "ska_oso_services.pht.service.security.facts.Facts.get_all_proposals_and_panels",
        autospec=True,
    )
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposal_list_success(self, mock_uow, mock_memberships, client_get):
        # Arrange
        proposal_objs = [TestDataFactory.proposal(), TestDataFactory.proposal()]
        proposal_ids = [p.prsl_id for p in proposal_objs]
        mock_memberships.return_value = SimpleNamespace(
            proposals={pid: object() for pid in proposal_ids},
            panels={},
        )

        uow = mock.MagicMock()
        uow.prsls.get.side_effect = lambda pid: next(
            (p for p in proposal_objs if p.prsl_id == pid), None
        )

        mock_uow.return_value.__enter__.return_value = uow
        mock_uow.return_value.__exit__.return_value = None

        resp = client_get(f"{PROPOSAL_API_URL}/mine")

        assert resp.status_code == HTTPStatus.OK, resp.json()
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == len(proposal_objs)
        mock_memberships.assert_called_once()

    @mock.patch(
        "ska_oso_services.pht.service.security.facts.Facts.get_all_proposals_and_panels",
        autospec=True,
    )
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposal_list_empty(self, mock_uow, mock_memberships, client_get):
        mock_memberships.return_value = SimpleNamespace(proposals={}, panels={})

        mock_uow.return_value.__enter__.return_value = mock.MagicMock()
        mock_uow.return_value.__exit__.return_value = None

        resp = client_get(f"{PROPOSAL_API_URL}/mine")
        assert resp.status_code == HTTPStatus.OK, resp.json()
        assert resp.json() == []


class TestProposalReadAccessFromClaims:
    def test_grants_read_for_proposal_member_group(self):
        auth = SimpleNamespace(
            user_id="u1",
            roles={prsl_api.Role.ANY},
            principals={"app:pht:prp-123"},
        )

        assert Facts(auth).is_member_of("prp-123") is True

    def test_grants_read_for_proposal_pi_group(self):
        auth = SimpleNamespace(
            user_id="u1",
            roles={prsl_api.Role.ANY},
            principals={"app:pht:prp-123/w/a"},
        )

        assert Facts(auth).is_pi("prp-123") is True

    def test_grants_read_for_global_admin_group(self):
        auth = SimpleNamespace(
            user_id="u1",
            roles={prsl_api.Role.ANY},
            principals={"app:pht:ops_proposal_admin"},
        )

        assert Facts(auth).is_pht_admin() is True

    def test_denies_read_for_unrecognized_groups(self):
        auth = SimpleNamespace(
            user_id="u1",
            roles={prsl_api.Role.ANY},
            principals={"some:other:group", "foo"},
        )

        assert Facts(auth).is_member_of("prp-123") is False


class TestGetProposalReview:
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_reviews_for_proposal_with_wrong_id(self, mock_oda, client):
        """
        Test reviews for a proposal with a wrong ID returns an empty list.
        """
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = []
        mock_oda.return_value.__enter__.return_value = uow_mock

        prsl_id = "prp-twrng2d"
        response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    @mock.patch(f"{PRSL_MODULE}.oda.uow")
    def test_get_reviews_for_panel_with_valid_id(self, mock_oda, client):
        """
        Test reviews for a proposal with a valid ID returns the expected reviews.
        """
        review_objs = [TestDataFactory.reviews(prsl_id="prp-tmyprp2")]
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = review_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        prsl_id = "prp-tmyprp2"
        response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")
        assert response.status_code == HTTPStatus.OK

        expected = [obj.model_dump(mode="json", exclude={"metadata"}) for obj in review_objs]
        payload = response.json()
        # align shapes by dropping metadata
        del payload[0]["metadata"]
        assert expected == payload
        assert payload[0]["review_id"] == expected[0]["review_id"]
        assert payload[0]["panel_id"] == expected[0]["panel_id"]


class TestPutProposalAPI:
    @staticmethod
    def _non_member_headers() -> dict[str, str]:
        token = mint_test_token(
            audience="test:pht",
            roles=[Role.ANY],
            scopes=[Scope.PHT_READ, Scope.PHT_READWRITE],
            groups=[],
        )
        return {
            "Content-type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    @pytest.mark.parametrize(
        "proposal_status,permissions",
        [
            ("submitted", ["submit", "view"]),
            ("submitted", ["submit"]),
            ("draft", ["update", "view"]),
            ("draft", ["update"]),
        ],
    )
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_proposal_put_success(self, mock_uow, proposal_status, permissions, client):
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
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_proposal_put_forbidden(
        self, mock_uow, proposal_status, permissions, client
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

        result = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers=self._non_member_headers(),
        )

        assert result.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "proposal_status,permissions",
        [
            ("submitted", ["view", "update"]),
        ],
    )
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
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
            headers=self._non_member_headers(),
        )

        assert result.status_code == HTTPStatus.FORBIDDEN

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_update_proposal_not_found(self, mock_uow, client):
        """
        Should return 404 if proposal doesn't exist.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_update_proposal_id_mismatch(self, mock_uow, client):
        """
        Should raise 422 when ID in path != payload.
        """
        proposal_obj = TestDataFactory.proposal()
        path_id = "diff-id"

        response = client.put(
            f"{PROPOSAL_API_URL}/{path_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in response.json()["detail"].lower()

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_update_proposal_validation_error(self, mock_oda, client):
        """
        Should return 400 if .add() raises ValueError.
        """
        proposal_obj = TestDataFactory.proposal()
        proposal_id = proposal_obj.prsl_id

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.return_value = proposal_obj
        uow_mock.prsls.add.side_effect = ValueError("Invalid proposal content")
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PROPOSAL_API_URL}/{proposal_id}",
            data=proposal_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "validation error" in response.json()["detail"].lower()


class TestProposalBatch:
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposals_batch_all_found(self, mock_oda, client):
        proposal1 = TestDataFactory.proposal(prsl_id="prp-tska-00001")
        proposal2 = TestDataFactory.proposal(prsl_id="prp-tska-00002")
        prsl_map = {"prp-tska-00001": proposal1, "prp-tska-00002": proposal2}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = prsl_map.get
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/batch",
            json={"prsl_ids": ["prp-tska-00001", "prp-tska-00002"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert {obj["prsl_id"] for obj in data} == {"prp-tska-00001", "prp-tska-00002"}

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_get_proposals_batch_partial_found(self, mock_oda, client):
        proposal1 = TestDataFactory.proposal(prsl_id="prp-tska-00001")
        prsl_map = {"prp-tska-00001": proposal1}

        uow_mock = mock.MagicMock()
        uow_mock.prsls.get.side_effect = prsl_map.get
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PROPOSAL_API_URL}/batch",
            json={"prsl_ids": ["prp-tska-00001", "prp-tska-00004"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["prsl_id"] == "prp-tska-00001"

    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
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


class TestGetProposalsByStatus:
    @staticmethod
    def _security(user_id: str, is_admin: bool, panels: dict[str, object]):
        return SimpleNamespace(
            auth=SimpleNamespace(user_id=user_id),
            facts=SimpleNamespace(
                is_pht_admin=lambda: is_admin,
                get_all_proposals_and_panels=lambda: SimpleNamespace(proposals={}, panels=panels),
            ),
            proposals=SimpleNamespace(allowed_to_view=lambda *args: None),
        )

    @mock.patch(f"{PRSL_MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_admin_prefers_under_review_then_submitted(self, mock_uow, mock_latest):
        p_ur = TestDataFactory.complete_proposal(prsl_id="prsl-1", status="under review")
        p_sub_same = TestDataFactory.complete_proposal(prsl_id="prsl-1", status="submitted")
        p_sub_other = TestDataFactory.complete_proposal(prsl_id="prsl-2", status="submitted")

        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow

        uow.prsls.query.side_effect = [[p_ur], [p_sub_other, p_sub_same]]
        mock_latest.side_effect = lambda rows, key: rows or []

        security = self._security(user_id="admin", is_admin=True, panels={})
        result = get_proposals_by_status(security=security)

        assert [p.prsl_id for p in result] == ["prsl-1", "prsl-2"]

    @mock.patch(f"{PRSL_MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_panel_member_filters_to_panel_proposals(self, mock_uow, mock_latest):
        p_1 = TestDataFactory.complete_proposal(prsl_id="prsl-1", status="under review")
        p_2 = TestDataFactory.complete_proposal(prsl_id="prsl-2", status="under review")

        panel = SimpleNamespace(proposals=[SimpleNamespace(prsl_id="prsl-2")])

        uow = mock.MagicMock()
        uow.panels.get.return_value = panel
        mock_uow.return_value.__enter__.return_value = uow
        uow.prsls.query.side_effect = [[p_1, p_2], []]
        mock_latest.side_effect = lambda rows, key: rows or []

        security = self._security(user_id="member", is_admin=False, panels={"pnl-1": object()})
        result = get_proposals_by_status(security=security)

        assert [p.prsl_id for p in result] == ["prsl-2"]

    @mock.patch(f"{PRSL_MODULE}.get_latest_entity_by_id", autospec=True)
    @mock.patch(f"{PRSL_MODULE}.oda.uow", autospec=True)
    def test_non_admin_without_panels_gets_empty(self, mock_uow, mock_latest):
        uow = mock.MagicMock()
        mock_uow.return_value.__enter__.return_value = uow
        uow.prsls.query.side_effect = [[], []]
        mock_latest.side_effect = lambda rows, key: rows or []

        security = self._security(user_id="none", is_admin=False, panels={})
        result = get_proposals_by_status(security=security)

        assert result == []


class TestGetReviewerPrslIds:
    @mock.patch(f"{MODULE}.CustomQuery")
    def test_calls_query_with_reviewer_id(self, mock_cq):
        uow = mock.MagicMock()
        uow.rvws.query.return_value = []

        reviewer_id = "kjf"
        ids = ps.get_reviewer_prsl_ids(uow, reviewer_id)

        assert ids == set()

        mock_cq.assert_called_once_with(reviewer_id=reviewer_id)
        uow.rvws.query.assert_called_once_with(mock_cq.return_value)

    @mock.patch(f"{MODULE}.get_panel_prsl_ids", autospec=True)
    @mock.patch(f"{MODULE}.get_latest_entity_by_id", autospec=True)
    def test_dedupes_and_returns_only_valid_ids_with_factory(self, mock_latest, mock_panel_ids):
        uow = mock.MagicMock()
        rows = [
            TestDataFactory.reviews(review_id="r1", reviewer_id="kjf", prsl_id="p1"),
            TestDataFactory.reviews(review_id="r2", reviewer_id="kjf", prsl_id="p1"),
            TestDataFactory.reviews(review_id="r3", reviewer_id="kjf", prsl_id="p2"),
            SimpleNamespace(reviewer_id="kjf"),
        ]
        uow.rvws.query.return_value = rows

        mock_latest.side_effect = lambda r, key: r or []
        mock_panel_ids.return_value = {"p1", "p2"}

        ids = ps.get_reviewer_prsl_ids(uow, "kjf")

        assert ids == {"p1", "p2"}

        uow.rvws.query.assert_called_once()
        mock_latest.assert_called_once()
        assert mock_latest.call_args.args[1] == "review_id"
        mock_panel_ids.assert_called_once_with(uow, ps.SV_NAME)

    @mock.patch(f"{MODULE}.get_panel_prsl_ids", autospec=True)
    @mock.patch(f"{MODULE}.get_latest_entity_by_id", autospec=True)
    def test_ignores_non_object_rows_with_factory(self, mock_latest, mock_panel_ids):
        uow = mock.MagicMock()
        rows = [
            {"prsl_id": "p-dict"},
            TestDataFactory.reviews(review_id="r5", reviewer_id="kjf", prsl_id="p-obj"),
        ]
        uow.rvws.query.return_value = rows

        mock_latest.side_effect = lambda r, key: r or []

        mock_panel_ids.return_value = {"p-obj"}

        ids = ps.get_reviewer_prsl_ids(uow, "kjf")

        assert ids == {"p-obj"}

        uow.rvws.query.assert_called_once()
        mock_latest.assert_called_once()
        assert mock_latest.call_args.args[1] == "review_id"

        mock_panel_ids.assert_called_once_with(uow, ps.SV_NAME)

    @pytest.mark.parametrize("rv", [None, []])
    def test_handles_none_or_empty_results(self, rv):
        uow = mock.MagicMock()
        uow.rvws.query.return_value = rv

        ids = ps.get_reviewer_prsl_ids(uow, "kjf")
        assert ids == set()


class TestGetPanelPrslIds:
    def test_returns_ids_from_panel(self):
        uow = mock.MagicMock()
        panel_name = "Science Verification"

        uow.panels.query.return_value = [
            TestDataFactory.panel_basic(panel_id="panel-1", name=panel_name)
        ]

        uow.panels.get.return_value = TestDataFactory.panel_with_assignment(
            panel_id="panel-1",
            name=panel_name,
            proposals=[
                TestDataFactory.proposal_assignment(prsl_id="p1"),
                TestDataFactory.proposal_assignment(prsl_id="p2"),
                TestDataFactory.proposal_assignment(prsl_id="p2"),
            ],
        )
        got = get_panel_prsl_ids(uow, panel_name)
        assert got == {"p1", "p2"}

        uow.panels.query.assert_called_once()
        uow.panels.get.assert_called_once_with("panel-1")

    def test_no_panel_refs_returns_empty(self):
        uow = mock.MagicMock()
        uow.panels.query.return_value = []

        got = get_panel_prsl_ids(uow, "Nonexistent")
        assert got == set()
        uow.panels.get.assert_not_called()

    def test_panel_not_found_returns_empty(self):
        uow = mock.MagicMock()
        uow.panels.query.return_value = [
            TestDataFactory.panel_basic(panel_id="missing", name="Anything")
        ]
        uow.panels.get.return_value = None

        got = get_panel_prsl_ids(uow, "Any")
        assert got == set()

    def test_no_proposals_returns_empty(self):
        uow = mock.MagicMock()

        uow.panels.query.return_value = [
            TestDataFactory.panel_basic(panel_id="panel-1", name="SCience Verification")
        ]

        uow.panels.get.return_value = TestDataFactory.panel_with_assignment(
            panel_id="panel-1", name="SCience Verification", proposals=None
        )

        got = get_panel_prsl_ids(uow, "Any")
        assert got == set()

    def test_ignores_invalid_entries(self):
        uow = mock.MagicMock()
        uow.panels.query.return_value = [
            TestDataFactory.panel_basic(panel_id="panel-1", name="SCience Verification")
        ]

        uow.panels.get.return_value = SimpleNamespace(
            panel_id="panel-1",
            proposals=[
                SimpleNamespace(),
                SimpleNamespace(prsl_id=None),
                SimpleNamespace(prsl_id="p-ok"),
            ],
        )

        got = get_panel_prsl_ids(uow, "Any")
        assert got == {"p-ok"}


EMAIL_TEST_CASES = [
    (
        "user@example.com",
        [{"id": "1", "mail": "user@example.com", "displayName": "User"}],
        {"id": "1", "mail": "user@example.com", "displayName": "User"},
    ),
]


class TestGetUserEmail:
    @pytest.mark.parametrize("email, mock_return, expected_response", EMAIL_TEST_CASES)
    @mock.patch(f"{PRSL_MODULE}.UserPortalService.search_users", new_callable=mock.AsyncMock)
    def test_get_user_by_email_success(
        self, mock_search_users, email, mock_return, expected_response, client_get
    ):
        mock_search_users.return_value = {"items": mock_return}

        response = client_get(f"{PHT_BASE_API_URL}/prsls/member/{email}")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == expected_response

    @mock.patch(f"{PRSL_MODULE}.UserPortalService.search_users", new_callable=mock.AsyncMock)
    def test_get_user_by_email_user_not_found(self, mock_search_users, client_get):
        email = "no_user@example.com"
        mock_search_users.return_value = {"items": []}

        response = client_get(f"{PHT_BASE_API_URL}/prsls/member/{email}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json() == {"detail": f"User not found with email: {email}"}

    @mock.patch(f"{PRSL_MODULE}.UserPortalService.search_users", new_callable=mock.AsyncMock)
    def test_get_user_by_invalid_email_user_not_found(self, mock_search_users, client_get):
        email = "invalid*address@example.com"
        mock_search_users.return_value = {"items": []}

        response = client_get(f"{PHT_BASE_API_URL}/prsls/member/{email}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json() == {"detail": f"User not found with email: {email}"}
