# pylint: disable=missing-timeout
import json
import uuid
from http import HTTPStatus

from ..unit.util import VALID_PANEL_DECISION, TestDataFactory
from . import PHT_URL



def test_get_list_proposal_access_for_user(authrequests):
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
        decision_id = f"pnld-test-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.panel_decision(decision_id=decision_id)
        proposal_json = proposal.model_dump_json()

        response = authrequests.post(
            f"{PHT_URL}/panel-decisions/",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created reviews
    example_decision_id = created_ids[0]
    get_response = authrequests.get(f"{PHT_URL}/panel-decisions/{example_decision_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    user_id = get_response.json()["metadata"]["created_by"]

    # GET /list/{user_id}
    list_response = authrequests.get(f"{PHT_URL}/panel-decisions/list/{user_id}")
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
