"""
Component level tests for the /engineering paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster.
"""

import json
from datetime import datetime

from ska_oso_pdm import OSOExecutionBlock
from ska_oso_pdm._shared import TelescopeType
from ska_oso_pdm.execution_block import (
    PythonArguments,
    RequestResponse,
    ResponseWrapper,
)

from . import ENGINEERING_BASE_API_URL

TEST_DATETIME = datetime.fromisoformat("2000-01-01T00:00:00.000000+00:00")


class TestEBs:
    def test_create_eb(self, client):
        """
        Tests that POST /ebs/ creates an ExecutionBlock and returns the eb_id.
        """
        eb = OSOExecutionBlock(telescope=TelescopeType.SKA_MID)
        post_response = client.post(
            f"{ENGINEERING_BASE_API_URL}/ebs/",
            content=eb.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert post_response.status_code == 200
        result = post_response.json()
        assert result["eb_id"].startswith("eb-")
        assert result["telescope"] == "ska_mid"

    def test_create_eb_with_telescope_path_and_no_body(self, client):
        """
        Tests that POST /ebs/{telescope} remains backward compatible with no body.
        """
        post_response = client.post(f"{ENGINEERING_BASE_API_URL}/ebs/ska_mid")
        assert post_response.status_code == 200
        result = post_response.json()
        assert result["eb_id"].startswith("eb-")
        assert result["telescope"] == "ska_mid"

    def test_create_eb_then_add_request_response(self, client):
        """
        Tests the full flow: create an EB via POST, add a request_response
        via PATCH, then verify the EB state via GET.
        """
        # Create EB
        eb = OSOExecutionBlock(telescope=TelescopeType.SKA_MID)
        post_response = client.post(
            f"{ENGINEERING_BASE_API_URL}/ebs/",
            content=eb.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert post_response.status_code == 200
        eb_id = post_response.json()["eb_id"]

        # Add a request_response
        rr = RequestResponse(
            request="tests.component.test_engineering_api.dummy_function",
            request_args=PythonArguments(args=[1], kwargs={"second_param": "test"}),
            request_sent_at=TEST_DATETIME,
            response_received_at=TEST_DATETIME,
            status="OK",
            response=ResponseWrapper(result="'the test function returned a value'"),
        )
        patch_response = client.patch(
            f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}/request_response",
            content=rr.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert patch_response.status_code == 200

        # Retrieve the EB and verify
        get_response = client.get(f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}")
        assert get_response.status_code == 200

        result_eb = OSOExecutionBlock.model_validate_json(get_response.content)
        assert result_eb.eb_id == eb_id
        assert len(result_eb.request_responses) == 1
        assert result_eb.request_responses[0].status == "OK"
        assert result_eb.request_responses[0].request == rr.request
        assert result_eb.request_responses[0].response.result == rr.response.result

    def test_create_eb_then_set_status_observed(self, client):
        """
        Tests that PUT /ebs/{eb_id}/status/observed sets the EB status to Observed.
        """
        eb = OSOExecutionBlock(telescope=TelescopeType.SKA_MID)
        post_response = client.post(
            f"{ENGINEERING_BASE_API_URL}/ebs/",
            content=eb.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert post_response.status_code == 200
        eb_id = post_response.json()["eb_id"]

        put_response = client.put(
            f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}/status/observed"
        )
        assert put_response.status_code == 200

        result = put_response.json()
        assert result["entity_id"] == eb_id
        assert result["status"] == "Observed"

    def test_create_eb_then_set_status_failed(self, client):
        """
        Tests that PUT /ebs/{eb_id}/status/failed sets the EB status to Failed.
        """
        eb = OSOExecutionBlock(telescope=TelescopeType.SKA_MID)
        post_response = client.post(
            f"{ENGINEERING_BASE_API_URL}/ebs/",
            content=eb.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert post_response.status_code == 200
        eb_id = post_response.json()["eb_id"]

        put_response = client.put(
            f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}/status/failed"
        )
        assert put_response.status_code == 200

        result = put_response.json()
        assert result["entity_id"] == eb_id
        assert result["status"] == "Observing Failed"

    def test_add_labels(self, client):
        """
        Tests the full flow: create an EB via POST, add labels via PATCH,
        then verify the labels are persisted via GET.
        """
        # Create EB
        eb = OSOExecutionBlock(telescope=TelescopeType.SKA_MID)
        post_response = client.post(
            f"{ENGINEERING_BASE_API_URL}/ebs/",
            content=eb.model_dump_json(),
            headers={"Content-type": "application/json"},
        )
        assert post_response.status_code == 200
        eb_id = post_response.json()["eb_id"]

        # Add labels
        labels = {"env": "test", "run_id": 42.0, "dry_run": True}
        patch_response = client.patch(
            f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}/labels",
            content=json.dumps(labels),
            headers={"Content-type": "application/json"},
        )
        assert patch_response.status_code == 200

        # Verify labels persisted via GET
        get_response = client.get(f"{ENGINEERING_BASE_API_URL}/ebs/{eb_id}")
        assert get_response.status_code == 200
        result_eb = OSOExecutionBlock.model_validate_json(get_response.content)
        assert result_eb.labels == labels
