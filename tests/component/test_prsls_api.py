"""
Component level tests for the /oda/prsls paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

import json
import uuid
from http import HTTPStatus

import requests

from ..unit.util import VALID_NEW_PROPOSAL, TestDataFactory
from . import PHT_URL


def test_create_and_get_proposal():
    """
    Integration test for the POST /prsls/create endpoint
    and GET /prsls/{prsl_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = requests.post(
        f"{PHT_URL}/prsls/create",
        data=VALID_NEW_PROPOSAL,
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()
    assert isinstance(prsl_id, str), f"Expected string, got {type(prsl_id)}: {prsl_id}"

    # GET created proposal
    get_response = requests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()

    # Prepare expected payload from input
    expected_payload = json.loads(VALID_NEW_PROPOSAL)

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("prsl_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)

    assert actual_payload == expected_payload


def test_proposal_create_then_put():
    """
    Test that an entity POSTed to /prsls/create
    can then be updated with PUT /prsls/{identifier},
    and the version number increments as expected.
    """

    # POST a new proposal
    post_response = requests.post(
        f"{PHT_URL}/prsls/create",
        data=VALID_NEW_PROPOSAL,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content

    # The POST endpoint returns only the prsl_id as a string
    returned_prsl_id = post_response.json()
    expected_prsl_id = json.loads(VALID_NEW_PROPOSAL)["prsl_id"]
    assert returned_prsl_id == expected_prsl_id

    # GET proposal to fetch latest state
    get_response = requests.get(f"{PHT_URL}/prsls/{returned_prsl_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    original_proposal = get_response.json()
    initial_version = original_proposal["metadata"]["version"]

    # Modify content (simulate update)
    original_proposal["info"]["title"] = "Updated Title"
    proposal_to_update = json.dumps(original_proposal)

    # PUT updated proposal
    put_response = requests.put(
        f"{PHT_URL}/prsls/{returned_prsl_id}",
        data=proposal_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1


def test_get_list_proposals_for_user():
    """
    Integration test:
    - Create multiple proposals
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created proposals are returned
    """

    created_ids = []

    # Create 2 proposals with unique prsl_ids
    for _ in range(2):
        prsl_id = f"prsl-test-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.proposal(prsl_id=prsl_id)
        proposal_json = proposal.model_dump_json()

        response = requests.post(
            f"{PHT_URL}/prsls/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created proposals
    example_prsl_id = created_ids[0]
    get_response = requests.get(f"{PHT_URL}/prsls/{example_prsl_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    user_id = get_response.json()["metadata"]["created_by"]

    # GET /list/{user_id}
    list_response = requests.get(f"{PHT_URL}/prsls/list/{user_id}")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    proposals = list_response.json()
    assert isinstance(proposals, list), "Expected a list of proposals"
    assert len(proposals) >= 2, f"Expected at least 2 proposals, got {len(proposals)}"

    # Check that all created proposals are returned
    returned_ids = {p["prsl_id"] for p in proposals}
    for prsl_id in created_ids:
        assert (
            prsl_id in returned_ids
        ), f"Missing proposal {prsl_id} in GET /list/{user_id}"
