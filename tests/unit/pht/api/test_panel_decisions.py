"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus
from unittest import mock

from ska_db_oda.persistence.domain.errors import ODANotFound

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import VALID_PANEL_DECISION, TestDataFactory, assert_json_is_equal

PANEL_DECISION_API_URL = f"{PHT_BASE_API_URL}/panel-decisions"


def has_validation_error(detail, field: str) -> bool:
    return any(field in str(e.get("loc", [])) for e in detail)


class Testpanel_decisionAPI:
    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
    def test_create_panel_decision(self, mock_oda, client):
        """
        Panel_decision create method returns the expected decision_id and status code.
        """

        panel_decision_obj = TestDataFactory.panel_decision()

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.add.return_value = panel_decision_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{PANEL_DECISION_API_URL}/",
            data=VALID_PANEL_DECISION,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == panel_decision_obj.decision_id

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
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
            f"{PANEL_DECISION_API_URL}/",
            data=VALID_PANEL_DECISION,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a Decision" in data["detail"]

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
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

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
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

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
    def test_get_panel_decision_list_success(self, mock_oda, client):
        """
        Check if the get_panel_decisions_for_user returns panel_decisions correctly.
        """
        panel_decision_objs = [
            TestDataFactory.panel_decision(),
            TestDataFactory.panel_decision(),
        ]
        uow_mock = mock.MagicMock()
        uow_mock.pnlds.query.return_value = panel_decision_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "DefaultUser"
        response = client.get(f"{PANEL_DECISION_API_URL}/list/{user_id}")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == len(panel_decision_objs)

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
    def test_get_panel_decision_list_none(self, mock_oda, client):
        """
        Should return empty list if no panel decisions are found.
        """
        uow_mock = mock.MagicMock()
        uow_mock.pnlds.query.return_value = []
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "user123"
        response = client.get(f"{PANEL_DECISION_API_URL}/list/{user_id}")

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

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
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

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
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

    @mock.patch("ska_oso_services.pht.api.panel_decision.oda.uow", autospec=True)
    def test_update_panel_decision_validation_error(self, mock_oda, client):
        """
        Should return 400 if .add() raises ValueError.
        """
        panel_decision_obj = TestDataFactory.panel_decision()
        decision_id = panel_decision_obj.decision_id

        uow_mock = mock.MagicMock()
        uow_mock.pnlds.get.return_value = panel_decision_obj
        uow_mock.pnlds.add.side_effect = ValueError("Invalid panel_decision content")
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{PANEL_DECISION_API_URL}/{decision_id}",
            data=panel_decision_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "validation error" in response.json()["detail"].lower()
