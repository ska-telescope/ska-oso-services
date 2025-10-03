"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock

import pytest
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token
from ska_db_oda.persistence.domain.errors import ODANotFound

from ska_oso_services.common.auth import AUDIENCE, Permissions, Scope
from ska_oso_services.pht.api import panel_decision as api
from src.ska_oso_services.pht.models.domain import PrslRole
from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import VALID_PANEL_DECISION, TestDataFactory, assert_json_is_equal

PANEL_DECISION_API_URL = f"{PHT_BASE_API_URL}/panel/decision"
SEC_OBJ = api.get_panel_decisions_for_user.__annotations__["auth"].__metadata__[0]
SEC_DEP = SEC_OBJ.dependency

MODULE = "ska_oso_services.pht.api.panel_decision"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


class Testpanel_decisionAPI:
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_create_panel_decision(self, mock_oda, client):
        """
        Panel_decision create method returns the expected decision_id and status code.
        """

        panel_decision_obj = TestDataFactory.panel_decision()

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.add.return_value = panel_decision_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PANEL_DECISION_API_URL}/create",
            data=VALID_PANEL_DECISION,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == panel_decision_obj.decision_id

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_create_panel_decision_value_error_raises_bad_request(
        self, mock_oda, client
    ):
        """
        ValueError in panel_decision creation and ensure it raises BadRequestError.
        """

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.add.side_effect = ValueError("mock-failure")

        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PANEL_DECISION_API_URL}/create",
            data=VALID_PANEL_DECISION,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a Decision" in data["detail"]

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_get_panel_decision_not_found(self, mock_oda, client):
        """
        Ensure ODANotFound during get() raises NotFoundError (404).
        """
        decision_id = "prsl-missing-9999"

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.get.side_effect = ODANotFound(identifier=decision_id)
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PANEL_DECISION_API_URL}/{decision_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "could not be found" in response.json()["detail"]

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_get_panel_decision_success(self, mock_oda, client):
        """
        Ensure valid panel_decision ID returns the panel_decision object.
        """
        panel_decision = TestDataFactory.panel_decision()
        decision_id = panel_decision.decision_id

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.get.return_value = panel_decision
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PANEL_DECISION_API_URL}/{decision_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["decision_id"] == decision_id

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_get_panel_decision_list_success_by_group(self, mock_uow, client_get):

        uow = mock.MagicMock()
        uow.pnlds.query.return_value = []
        mock_uow.return_value.__enter__.return_value = uow

        resp = client_get(f"{PANEL_DECISION_API_URL}/")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == []

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_get_panel_decision_list_forbidden_when_no_allowed_role_or_group(
        self, mock_uow, client
    ):
        """
        403 when token lacks SW_ENGINEER role and has no allowed groups.
        """
        bad_token = mint_test_token(
            audience=AUDIENCE,
            roles=[Role.ANY],
            scopes=[Scope.PHT_READWRITE],
            groups=[],
        )

        uow = mock.MagicMock()
        uow.pnlds.query.return_value = []
        mock_uow.return_value.__enter__.return_value = uow

        resp = client.get(
            f"{PANEL_DECISION_API_URL}/",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == HTTPStatus.FORBIDDEN
        assert "permission" in resp.json()["detail"].lower()

    @mock.patch(
        "ska_oso_services.pht.api.panel_decision.Permissions.__call__", autospec=True
    )
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_get_panel_decision_list_none(self, mock_oda, mock_perm_call, client):
        """
        Should return empty list if no panel decisions are found.
        Requires ADMIN + CHAIR + SW_DEV in groups.
        """
        mock_perm_call.return_value = SimpleNamespace(
            groups={PrslRole.OPS_PROPOSAL_ADMIN, PrslRole.OPS_REVIEW_CHAIR}
        )

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.query.return_value = []
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{PANEL_DECISION_API_URL}/")
        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
    def test_panel_decision_put_success(self, mock_uow, client):
        """
        Check the prsls_put method returns the expected response
        """
        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True
        panel_decision_obj = TestDataFactory.panel_decision()
        decision_id = panel_decision_obj.decision_id
        uow_mock.pnlds.add.return_value = panel_decision_obj
        uow_mock.pnlds.get.return_value = panel_decision_obj
        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, panel_decision_obj.model_dump_json())

    @pytest.mark.parametrize(
        "recommendation",
        [
            "Accepted",
            "Accepted with Revision",
            "Rejected",
        ],
    )
    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_panel_decision_put_success_for_decided(
        self, mock_uow, client, recommendation
    ):
        """
        Check the pnlds_put method returns the expected response when status is decided
        """
        uow_mock = mock.MagicMock()
        uow_mock.pnlds.__contains__.return_value = True
        uow_mock.prsls.__contains__.return_value = True
        panel_decision_obj = TestDataFactory.panel_decision(
            status="Decided", recommendation=recommendation
        )
        decision_id = panel_decision_obj.decision_id
        uow_mock.pnlds.add.return_value = panel_decision_obj
        uow_mock.pnlds.get.return_value = panel_decision_obj
        uow_mock.prsls.get.return_value = TestDataFactory.proposal()

        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, panel_decision_obj.model_dump_json())
        uow_mock.prsls.add.assert_called_once()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_panel_decision_put_success_for_non_decided(self, mock_uow, client):
        """
        Check pnlds_put method returns expected response when status is not decided
        """
        uow_mock = mock.MagicMock()
        uow_mock.pnlds.__contains__.return_value = True
        uow_mock.prsls.__contains__.return_value = True
        panel_decision_obj = TestDataFactory.panel_decision(
            status="In Progress", recommendation="Accepted"
        )
        decision_id = panel_decision_obj.decision_id
        uow_mock.pnlds.add.return_value = panel_decision_obj
        uow_mock.pnlds.get.return_value = panel_decision_obj
        uow_mock.prsls.get.return_value = TestDataFactory.proposal()

        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, panel_decision_obj.model_dump_json())
        uow_mock.prsls.get.assert_not_called()
        uow_mock.prsls.add.assert_not_called()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_decision_not_found(self, mock_uow, client):
        """
        Should return 404 if panel_decision doesn't exist.
        """
        panel_decision_obj = TestDataFactory.panel_decision()
        decision_id = panel_decision_obj.decision_id

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_proposal_not_found(self, mock_uow, client):
        """
        Should return 404 if proposal doesn't exist.
        """
        panel_decision_obj = TestDataFactory.panel_decision(
            status="Decided", recommendation="Accepted"
        )

        decision_id = panel_decision_obj.decision_id

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.add.return_value = panel_decision_obj
        uow_mock.pnlds.get.return_value = panel_decision_obj
        uow_mock.prsls.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_decision_id_mismatch(self, mock_uow, client):
        """
        Should raise 422 when ID in path != payload.
        """
        panel_decision_obj = TestDataFactory.panel_decision()
        path_id = "diff-id"

        response = client.put(
            f"{PANEL_DECISION_API_URL}/{path_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in response.json()["detail"].lower()

    @mock.patch(f"{MODULE}.oda.uow", autospec=True)
    def test_update_panel_decision_validation_error(self, mock_oda, client):
        """
        Should return 400 if .add() raises ValueError (auth passes).
        """
        panel_decision_obj = TestDataFactory.panel_decision()
        decision_id = panel_decision_obj.decision_id

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.get.return_value = panel_decision_obj  # found existing
        uow_mock.pnlds.add.side_effect = ValueError("Invalid panel_decision content")
        mock_oda.return_value.__enter__.return_value = uow_mock

        resp = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "validation" in resp.json()["detail"].lower()
