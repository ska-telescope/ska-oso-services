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
    can then be updated with PUT /proposals/{identifier}
    """
    post_response = requests.post(
        f"{PPT_URL}/proposals",
        data=VALID_NEW_PROPOSAL,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        VALID_NEW_PROPOSAL,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    prsl_id = post_response.json()
    proposal_to_update = TestDataFactory.proposal(prsl_id=prsl_id).model_dump_json()
    put_response = requests.put(
        f"{PPT_URL}/proposals/{prsl_id}",
        data=proposal_to_update,
        headers={"Content-type": "application/json"},
    )
    # Assert the ODT can get the proposal, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert put_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        put_response.content,
        proposal_to_update,
        exclude_paths=["root['metadata']", "root['prsl_id']"],
    )
    assert put_response.json()["metadata"]["version"] == 2
