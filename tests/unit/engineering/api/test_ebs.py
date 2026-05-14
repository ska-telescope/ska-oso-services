"""
Unit tests for ska_oso_services.engineering.api.ebs
"""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from ska_db_oda.postgres.mapping import Status, StatusLabel
from ska_db_oda.repository.domain import ODANotFound
from ska_oso_pdm import OSOExecutionBlock as ExecutionBlock
from ska_oso_pdm import TelescopeType
from ska_oso_pdm._shared import PythonArguments
from ska_oso_pdm.execution_block import RequestResponse, ResponseWrapper

from tests.unit.conftest import APP_BASE_API_URL

EBS_API_URL = f"{APP_BASE_API_URL}/engineering/ebs"


def make_eb(eb_id="eb-test-123", telescope=TelescopeType.SKA_MID, request_responses=None):
    kwargs = {"eb_id": eb_id, "telescope": telescope}
    if request_responses is not None:
        kwargs["request_responses"] = request_responses
    return ExecutionBlock(**kwargs)


def make_request_response():
    return RequestResponse(
        request="some.module.function",
        request_args=PythonArguments(args=[1], kwargs={"param": "value"}),
        status="OK",
        response=ResponseWrapper(result="'a result'"),
    )


class TestGetEB:
    def test_get_existing_eb(self, client_with_uow_mock):
        """GET /ebs/{eb_id} returns the EB when it exists in the ODA."""
        client, uow_mock = client_with_uow_mock
        eb = make_eb()
        uow_mock.ebs.get.return_value = eb

        response = client.get(f"{EBS_API_URL}/eb-test-123")

        assert response.status_code == HTTPStatus.OK
        result = ExecutionBlock.model_validate_json(response.text)
        assert result.eb_id == "eb-test-123"
        assert result.telescope == TelescopeType.SKA_MID
        uow_mock.ebs.get.assert_called_once_with("eb-test-123")

    def test_get_eb_not_found(self, client_with_uow_mock):
        """GET /ebs/{eb_id} returns 404 when the EB does not exist."""
        client, uow_mock = client_with_uow_mock
        uow_mock.ebs.get.side_effect = ODANotFound(identifier="eb-missing")

        response = client.get(f"{EBS_API_URL}/eb-missing")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "eb-missing" in response.json()["detail"]


class TestCreateEB:
    def test_create_eb_for_mid(self, client_with_uow_mock):
        """POST /ebs/{telescope} creates and returns a new EB for SKA_MID."""
        client, uow_mock = client_with_uow_mock
        persisted_eb = make_eb(telescope=TelescopeType.SKA_MID)
        uow_mock.ebs.add.return_value = persisted_eb

        response = client.post(f"{EBS_API_URL}/ska_mid")

        assert response.status_code == HTTPStatus.OK
        result = ExecutionBlock.model_validate_json(response.text)
        assert result.telescope == TelescopeType.SKA_MID
        uow_mock.ebs.add.assert_called_once()
        uow_mock.commit.assert_called_once()

    def test_create_eb_for_low(self, client_with_uow_mock):
        """POST /ebs/{telescope} creates and returns a new EB for SKA_LOW."""
        client, uow_mock = client_with_uow_mock
        persisted_eb = make_eb(telescope=TelescopeType.SKA_LOW)
        uow_mock.ebs.add.return_value = persisted_eb

        response = client.post(f"{EBS_API_URL}/ska_low")

        assert response.status_code == HTTPStatus.OK
        result = ExecutionBlock.model_validate_json(response.text)
        assert result.telescope == TelescopeType.SKA_LOW


class TestAddRequestResponse:
    def test_add_request_response_appends_to_existing(self, client_with_uow_mock):
        """PATCH /ebs/{eb_id}/request_response appends to an existing list."""
        client, uow_mock = client_with_uow_mock
        existing_rr = make_request_response()
        eb = make_eb(request_responses=[existing_rr])
        new_rr = make_request_response()
        updated_eb = make_eb(request_responses=[existing_rr, new_rr])

        uow_mock.ebs.get.return_value = eb
        uow_mock.ebs.add.return_value = updated_eb

        response = client.patch(
            f"{EBS_API_URL}/eb-test-123/request_response",
            content=new_rr.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        result = ExecutionBlock.model_validate_json(response.text)
        assert len(result.request_responses) == 2
        uow_mock.ebs.get.assert_called_once_with("eb-test-123")
        uow_mock.ebs.add.assert_called_once()
        uow_mock.commit.assert_called_once()

    def test_add_request_response_when_none(self, client_with_uow_mock):
        """PATCH /ebs/{eb_id}/request_response initialises the list when it is None."""
        client, uow_mock = client_with_uow_mock
        # Simulate an EB fetched from the DB where request_responses is null
        mock_eb = MagicMock()
        mock_eb.request_responses = None
        new_rr = make_request_response()
        updated_eb = make_eb(request_responses=[new_rr])

        uow_mock.ebs.get.return_value = mock_eb
        uow_mock.ebs.add.return_value = updated_eb

        response = client.patch(
            f"{EBS_API_URL}/eb-test-123/request_response",
            content=new_rr.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        result = ExecutionBlock.model_validate_json(response.text)
        assert len(result.request_responses) == 1

    def test_add_request_response_eb_not_found(self, client_with_uow_mock):
        """PATCH /ebs/{eb_id}/request_response returns 404 when the EB does not exist."""
        client, uow_mock = client_with_uow_mock
        uow_mock.ebs.get.side_effect = ODANotFound(identifier="eb-missing")
        new_rr = make_request_response()

        response = client.patch(
            f"{EBS_API_URL}/eb-missing/request_response",
            content=new_rr.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "eb-missing" in response.json()["detail"]


def make_status(entity_id="eb-test-123", status="Observed", updated_by="test-user"):
    return Status(entity_id=entity_id, status=status, updated_by=updated_by)


class TestSetEBStatusObserved:
    def test_set_status_observed_returns_updated_status(self, client_with_uow_mock):
        """
        PUT /ebs/{eb_id}/status/observed calls
        update_status with OBSERVED and returns Status.
        """
        client, uow_mock = client_with_uow_mock
        returned_status = make_status(status=StatusLabel.OBSERVED)
        uow_mock.status.get_current_status.return_value = returned_status

        response = client.put(f"{EBS_API_URL}/eb-test-123/status/observed")

        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["entity_id"] == "eb-test-123"
        assert result["status"] == StatusLabel.OBSERVED
        uow_mock.status.update_status.assert_called_once_with(
            entity_id="eb-test-123",
            status=StatusLabel.OBSERVED,
        )
        uow_mock.commit.assert_called_once()
        uow_mock.status.get_current_status.assert_called_once_with(entity_id="eb-test-123")

    def test_set_status_observed_propagates_oda_error(self, client_with_uow_mock):
        """PUT /ebs/{eb_id}/status/observed propagates errors from the status repository."""
        client, uow_mock = client_with_uow_mock
        uow_mock.status.update_status.side_effect = RuntimeError("ODA error")

        with pytest.raises(RuntimeError):
            response = client.put(f"{EBS_API_URL}/eb-test-123/status/observed")
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestSetEBStatusFailed:
    def test_set_status_failed_returns_updated_status(self, client_with_uow_mock):
        """PUT /ebs/{eb_id}/status/failed calls update_status with FAILED and returns Status."""
        client, uow_mock = client_with_uow_mock
        returned_status = make_status(status=StatusLabel.FAILED)
        uow_mock.status.get_current_status.return_value = returned_status

        response = client.put(f"{EBS_API_URL}/eb-test-123/status/failed")

        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["entity_id"] == "eb-test-123"
        assert result["status"] == StatusLabel.FAILED
        uow_mock.status.update_status.assert_called_once_with(
            entity_id="eb-test-123",
            status=StatusLabel.FAILED,
        )
        uow_mock.commit.assert_called_once()
        uow_mock.status.get_current_status.assert_called_once_with(entity_id="eb-test-123")

    def test_set_status_failed_propagates_oda_error(self, client_with_uow_mock):
        """PUT /ebs/{eb_id}/status/failed propagates errors from the status repository."""
        client, uow_mock = client_with_uow_mock
        uow_mock.status.update_status.side_effect = RuntimeError("ODA error")

        with pytest.raises(RuntimeError):
            response = client.put(f"{EBS_API_URL}/eb-test-123/status/failed")
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
