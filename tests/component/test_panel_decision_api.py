"""
Component level tests for the /oda/reviews paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
import json
from http import HTTPStatus

from ..unit.util import TestDataFactory
from . import PHT_URL


def test_create_and_get_panel_decision(authrequests, test_panel_id):
    """
    Integration test for the POST /panel/decision/ endpoint
    and GET /panel/decision/{decision_id}.
    Assumes the server is running and accessible.
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    panel_decision_json = TestDataFactory.panel_decision(
        prsl_id=prsl_id, panel_id=test_panel_id
    ).model_dump_json()
    # POST using JSON string
    post_response = authrequests.post(
        f"{PHT_URL}/panel/decision/create",
        data=panel_decision_json,
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    decision_id = post_response.json()
    assert isinstance(decision_id, str), f"Expected string, got {type(decision_id)}: {decision_id}"

    # GET created proposal
    get_response = authrequests.get(f"{PHT_URL}/panel/decision/{decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()

    # Prepare expected payload from input
    expected_payload = json.loads(panel_decision_json)

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("decision_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)

    assert actual_payload == expected_payload


def test_panel_decision_create_then_put(authrequests, test_panel_id):
    """
    Test that an entity POSTed to /panel-decision/create
    can then be updated with PUT /panel-decision/{identifier},
    and the version number increments as expected.
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    # POST a new proposal
    decision = TestDataFactory.panel_decision(prsl_id=prsl_id, panel_id=test_panel_id)
    post_response = authrequests.post(
        f"{PHT_URL}/panel/decision/create",
        data=decision.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content

    # The POST endpoint returns only the decision_idas a string
    returned_decision_id = post_response.json()
    assert returned_decision_id == decision.decision_id

    # GET proposal to fetch latest state
    get_response = authrequests.get(f"{PHT_URL}/panel/decision/{returned_decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    originalreview = get_response.json()
    initial_version = originalreview["metadata"]["version"]

    # Modify content (simulate update)
    review_to_update = json.dumps(originalreview)

    # PUT updated proposal
    put_response = authrequests.put(
        f"{PHT_URL}/panel/decision/{returned_decision_id}",
        data=review_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1


def test_panel_decision_put_decided_updates_proposal(authrequests, test_panel_id):
    # create a new proposal
    post_prsl_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    prsl_id = post_prsl_response.json()["prsl_id"]

    # create a new decision with prsl_id
    decision = TestDataFactory.panel_decision(prsl_id=prsl_id, panel_id=test_panel_id)
    post_decision_response = authrequests.post(
        f"{PHT_URL}/panel/decision/create",
        data=decision.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    decision_id = post_decision_response.json()

    # GET decision to fetch latest state
    get_decision_response = authrequests.get(f"{PHT_URL}/panel/decision/{decision_id}")

    originaldecision = get_decision_response.json()

    initial_version = originaldecision["metadata"]["version"]

    # Update decision to decided and recommendation accepted
    originaldecision["status"] = "Decided"
    originaldecision["recommendation"] = "Accepted"
    review_to_update = json.dumps(originaldecision)

    # PUT updated proposal
    put_response = authrequests.put(
        f"{PHT_URL}/panel/decision/{decision_id}",
        data=review_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1

    # GET proposal to fetch latest state
    get_proposal_after_updated = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")

    # Confirm proposal status updated
    assert get_proposal_after_updated.json()["status"] == "accepted"


def test_panel_decision_put_not_decided_not_updating_proposal(authrequests, test_panel_id):
    # create a new proposal
    proposal = TestDataFactory.proposal()
    post_prsl_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    prsl_id = post_prsl_response.json()["prsl_id"]

    # create a new decision with prsl_id
    decision = TestDataFactory.panel_decision(prsl_id=prsl_id, panel_id=test_panel_id)

    post_decision_response = authrequests.post(
        f"{PHT_URL}/panel/decision/create",
        data=decision.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    decision_id = post_decision_response.json()

    # GET decision to fetch latest state
    get_decision_response = authrequests.get(f"{PHT_URL}/panel/decision/{decision_id}")

    originaldecision = get_decision_response.json()

    print(originaldecision)

    initial_version = originaldecision["metadata"]["version"]

    # use default status for panel decision
    review_to_update = json.dumps(originaldecision)

    # PUT updated proposal
    put_response = authrequests.put(
        f"{PHT_URL}/panel/decision/{decision_id}",
        data=review_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1

    # GET proposal to fetch latest state
    get_proposal_after_updated = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")

    # Confirm proposal status not updated
    assert get_proposal_after_updated.json()["status"] == proposal.status


def test_get_list_panel_decision_for_user(authrequests, test_panel_id):
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
        # Add proposal to link to
        post_response = authrequests.post(
            f"{PHT_URL}/prsls/create",
            data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prsl_id = post_response.json()["prsl_id"]
        panel_decision = TestDataFactory.panel_decision(prsl_id=prsl_id, panel_id=test_panel_id)

        response = authrequests.post(
            f"{PHT_URL}/panel/decision/create",
            data=panel_decision.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created reviews
    example_decision_id = created_ids[0]
    get_response = authrequests.get(f"{PHT_URL}/panel/decision/{example_decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    list_response = authrequests.get(f"{PHT_URL}/panel/decision/")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    reviews = list_response.json()
    assert isinstance(reviews, list), "Expected a list of reviews"
    assert len(reviews) >= 2, f"Expected at least 2 reviews, got {len(reviews)}"

    # Check that all created reviews are returned
    returned_ids = {p["decision_id"] for p in reviews}
    for decision_id in created_ids:
        assert decision_id in returned_ids, f"Missing proposal {decision_id} in GET /"
