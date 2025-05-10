"""
Component level tests for the /oda/proposals paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
import json
from http import HTTPStatus

import requests

from ..unit.util import VALID_NEW_PROPOSAL, TestDataFactory, assert_json_is_equal
from . import PPT_URL


def test_create_and_get_proposal():
    """
    Integration test for the POST /proposal/create endpoint
    and GET /proposals/{prsl_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = requests.post(
        f"{PPT_URL}/proposals/create",
        data=VALID_NEW_PROPOSAL,
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()
    assert isinstance(prsl_id, str), f"Expected string, got {type(prsl_id)}: {prsl_id}"

    # GET created proposal
    get_response = requests.get(f"{PPT_URL}/proposals/{prsl_id}")
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
    Test that an entity POSTed to /proposals/create
    can then be updated with PUT /proposals/{identifier},
    and the version number increments as expected.
    """

    #POST a new proposal
    post_response = requests.post(
        f"{PPT_URL}/proposals/create",
        data=VALID_NEW_PROPOSAL,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content

    # The POST endpoint returns only the prsl_id as a string
    returned_prsl_id = post_response.json()
    expected_prsl_id = json.loads(VALID_NEW_PROPOSAL)["prsl_id"]
    assert returned_prsl_id == expected_prsl_id

    #GET the proposal to get initial version
    get_response = requests.get(f"{PPT_URL}/proposals/{returned_prsl_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    initial_version = get_response.json()["metadata"]["version"]

    # Step 3: Generate update and enforce prsl_id match
    proposal = TestDataFactory.proposal(prsl_id=returned_prsl_id)
    proposal_to_update = proposal.model_dump_json()

    #PUT updated proposal
    put_response = requests.put(
        f"{PPT_URL}/proposals/{returned_prsl_id}",
        data=proposal_to_update,
        headers={"Content-Type": "application/json"},
    )

    assert put_response.status_code == HTTPStatus.OK, put_response.content

    #Compare JSON output
    assert_json_is_equal(
        put_response.text,
        proposal_to_update,
        exclude_paths=["root['metadata']", "root['prsl_id']"]
    )

    # Ensure version incremented
    new_version = put_response.json()["metadata"]["version"]
    assert new_version == initial_version + 1, f"Expected version {initial_version + 1}, got {new_version}"