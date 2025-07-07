"""
Component level tests for the /oda/reviews paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
import json
import uuid
from http import HTTPStatus

import requests

from ..unit.util import VALID_PANEL_DECISION, TestDataFactory
from . import PHT_URL


def test_create_and_get_panel_decision():
    """
    Integration test for the POST /panel-decision/create endpoint
    and GET /panel-decision/{decision_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = requests.post(
        f"{PHT_URL}/panel-decisions/create",
        data=VALID_PANEL_DECISION,
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    decision_id= post_response.json()
    assert isinstance(
        decision_id, str
    ), f"Expected string, got {type(decision_id)}: {decision_id}"

    # GET created proposal
    get_response = requests.get(f"{PHT_URL}/panel-decisions/{decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()

    # Prepare expected payload from input
    expected_payload = json.loads(VALID_PANEL_DECISION)

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("decision_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)

    assert actual_payload == expected_payload


def test_panel_decision_create_then_put():
    """
    Test that an entity POSTed to /panel-decision/create
    can then be updated with PUT /panel-decision/{identifier},
    and the version number increments as expected.
    """

    # POST a new proposal
    post_response = requests.post(
        f"{PHT_URL}/panel-decisions/",
        data=VALID_PANEL_DECISION,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content

    # The POST endpoint returns only the decision_idas a string
    returned_decision_id= post_response.json()
    expected_decision_id= json.loads(VALID_PANEL_DECISION)["decision_id"]
    assert returned_decision_id== expected_decision_id

    # GET proposal to fetch latest state
    get_response = requests.get(f"{PHT_URL}/panel-decisions/{returned_decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    originalreview = get_response.json()
    initial_version = originalreview["metadata"]["version"]

    # Modify content (simulate update)
    review_to_update = json.dumps(originalreview)

    # PUT updated proposal
    put_response = requests.put(
        f"{PHT_URL}/panel-decisions/{returned_decision_id}",
        data=review_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1


def test_get_list_panel_decision_for_user():
    """
    Integration test:
    - Create multiple reviews
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created panel-decision are returned
    """

    created_ids = []

    # Create 2 reviews with unique decision_ids
    for _ in range(2):
        decision_id= f"pnld-test-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.panel_decision(decision_id=decision_id)
        proposal_json = proposal.model_dump_json()

        response = requests.post(
            f"{PHT_URL}/panel-decisions/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created reviews
    example_decision_id= created_ids[0]
    get_response = requests.get(f"{PHT_URL}/panel-decisions/{example_decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    user_id = get_response.json()["metadata"]["created_by"]

    # GET /list/{user_id}
    list_response = requests.get(f"{PHT_URL}/panel-decisions/list/{user_id}")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    reviews = list_response.json()
    assert isinstance(reviews, list), "Expected a list of reviews"
    assert len(reviews) >= 2, f"Expected at least 2 reviews, got {len(reviews)}"

    # Check that all created reviews are returned
    returned_ids = {p["decision_id"] for p in reviews}
    for decision_id in created_ids:
        assert (
            decision_id in returned_ids
        ), f"Missing proposal {decision_id} in GET /list/{user_id}"
