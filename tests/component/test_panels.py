import uuid
from http import HTTPStatus

import requests

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/panels"
HEADERS = {"Content-type": "application/json"}


def test_create_panel():
    panel = TestDataFactory.panel_basic()
    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert panel.panel_id == result


def test_panels_post_duplicate_reviewer():
    panel = TestDataFactory.panel()
    panel.reviewers.append(panel.reviewers[0])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT

    result = response.json()
    expected = {"detail": "Duplicate reviewer_id are not allowed: {'rev-001'}"}
    assert expected == result


def test_panels_post_duplicate_proposal():
    panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])
    panel.proposals.append(panel.proposals[0])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT

    result = response.json()
    expected = {"detail": "Duplicate prsl_id are not allowed: {'prop-astro-01'}"}
    assert expected == result


def test_panels_post_not_existing_reviewer():
    panel = TestDataFactory.panel()

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Reviewer 'rev-001' does not exist"}
    assert expected == result


def test_panels_post_not_existing_proposal():
    panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Proposal 'prop-astro-01' does not exist"}
    assert expected == result

def test_get_list_panels_for_user():
    """
    Integration test:
    - Create multiple panels
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created panels are returned
    """

    created_ids = []

    # Create 2 proposals with unique prsl_ids
    for _ in range(2):
        panel_id = f"panel-test-{uuid.uuid4().hex[:8]}"
        panel = TestDataFactory.panel(panel_id=panel_id)
        panel_json = panel.model_dump_json()

        response = requests.post(
            PANELS_API_URL,
            data=panel_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created panels
    example_panel_id = created_ids[0]
    get_response = requests.get(f"{PANELS_API_URL}/{example_panel_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    user_id = get_response.json()["metadata"]["created_by"]

    # GET /list/{user_id}
    list_response = requests.get(f"{PANELS_API_URL}/list/{user_id}")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    panels = list_response.json()
    assert isinstance(panels, list), "Expected a list of proposals"
    assert len(panels) >= 2, f"Expected at least 2 proposals, got {len(panels)}"

    # Check that all created proposals are returned
    returned_ids = {p["panel_id"] for p in panels}
    for panel_id in created_ids:
        assert (
            panel_id in returned_ids
        ), f"Missing proposal {panel_id} in GET /list/{user_id}"
