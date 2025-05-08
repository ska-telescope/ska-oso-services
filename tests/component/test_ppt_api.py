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

from ..unit.util import load_string_from_file
from . import PHT_URL


def test_create_proposal():
    """
    Integration test for the POST /proposal/create endpoint.
    Assumes the server is running and accessible.
    """

    # Parse JSON into Proposal model
    prsl = Proposal.model_validate_json(
        load_string_from_file("../unit/files/create_proposal.json")
    )

    # Convert back to JSON dict for POST request
    proposal_payload = json.loads(prsl.model_dump_json())

    response = requests.post(
        f"{PHT_URL}/proposal/create",
        json=proposal_payload,
        headers={"Content-Type": "application/json"},
    )
    assert (
        response.status_code == HTTPStatus.OK
    ), f"Failed with status {response.status_code}: {response.text}"
    result = response.json()
    assert isinstance(result, str), f"Expected string, got {type(result)}: {result}"
