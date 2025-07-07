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

from ..unit.util import VALID_REVIEW, TestDataFactory
from . import PHT_URL


def test_create_and_get_review():
    """
    Integration test for the POST /reviews/create endpoint
    and GET /reviews/{review_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = requests.post(
        f"{PHT_URL}/reviews/create",
        data=VALID_REVIEW,
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    review_id = post_response.json()
    assert isinstance(
        review_id, str
    ), f"Expected string, got {type(review_id)}: {review_id}"

    # GET created proposal
    get_response = requests.get(f"{PHT_URL}/reviews/{review_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()

    # Prepare expected payload from input
    expected_payload = json.loads(VALID_REVIEW)

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("review_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)

    assert actual_payload == expected_payload


def testreview_create_then_put():
    """
    Test that an entity POSTed to /reviews/create
    can then be updated with PUT /reviews/{identifier},
    and the version number increments as expected.
    """

    # POST a new proposal
    post_response = requests.post(
        f"{PHT_URL}/reviews/create",
        data=VALID_REVIEW,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content

    # The POST endpoint returns only the review_id as a string
    returned_review_id = post_response.json()
    expected_review_id = json.loads(VALID_REVIEW)["review_id"]
    assert returned_review_id == expected_review_id

    # GET proposal to fetch latest state
    get_response = requests.get(f"{PHT_URL}/reviews/{returned_review_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    originalreview = get_response.json()
    initial_version = originalreview["metadata"]["version"]

    # Modify content (simulate update)
    originalreview["info"]["title"] = "Updated Title"
    review_to_update = json.dumps(originalreview)

    # PUT updated proposal
    put_response = requests.put(
        f"{PHT_URL}/reviews/{returned_review_id}",
        data=review_to_update,
        headers={"Content-Type": "application/json"},
    )

    # Confirm version bumped
    assert put_response.json()["metadata"]["version"] == initial_version + 1


def test_get_listreviews_for_user():
    """
    Integration test:
    - Create multiple reviews
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created reviews are returned
    """

    created_ids = []

    # Create 2 reviews with unique review_ids
    for _ in range(2):
        review_id = f"prsl-test-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.proposal(review_id=review_id)
        proposal_json = proposal.model_dump_json()

        response = requests.post(
            f"{PHT_URL}/reviews/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created reviews
    example_review_id = created_ids[0]
    get_response = requests.get(f"{PHT_URL}/reviews/{example_review_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    user_id = get_response.json()["metadata"]["created_by"]

    # GET /list/{user_id}
    list_response = requests.get(f"{PHT_URL}/reviews/list/{user_id}")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    reviews = list_response.json()
    assert isinstance(reviews, list), "Expected a list of reviews"
    assert len(reviews) >= 2, f"Expected at least 2 reviews, got {len(reviews)}"

    # Check that all created reviews are returned
    returned_ids = {p["review_id"] for p in reviews}
    for review_id in created_ids:
        assert (
            review_id in returned_ids
        ), f"Missing proposal {review_id} in GET /list/{user_id}"
