"""
Component level tests for the /oda/sbds paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
import json
from http import HTTPStatus

import requests
from ska_oso_pdm.proposal import Proposal

# from ..unit.util import load_string_from_file

from ..unit.util import (
    VALID_NEW_PROPOSAL,
    TestDataFactory,
    assert_json_is_equal,
)

from . import PHT_URL


def test_create_and_get_proposal():
    """
    Integration test for the POST /proposal/create endpoint.
    Assumes the server is running and accessible.
    """

    post_response = requests.post(
        f"{PHT_URL}/proposals/create",
        json=VALID_NEW_PROPOSAL,
        headers={"Content-Type": "application/json"},
    )
    assert (
        post_response.status_code == HTTPStatus.OK
    ), f"Failed with status {post_response.status_code}: {post_response.text}"
    result = post_response.json()
    assert isinstance(result, str), f"Expected string, got {type(result)}: {result}"

    prsl_id = post_response.json()["proposal_id"]
    get_response = requests.get(f"{PHT_URL}/proposals/{prsl_id}")

    # Assert the PPT can get the proposal, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()
    expected_payload = VALID_NEW_PROPOSAL
    for obj in (actual_payload, expected_payload):
        obj.pop("prsl_id", None)
        if "metadata" in obj:
            obj["metadata"].pop("created_on", None)
            obj["metadata"].pop("last_modified_on", None)

    assert actual_payload == expected_payload
