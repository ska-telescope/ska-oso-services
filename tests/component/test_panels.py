import uuid
from http import HTTPStatus

import requests
from ska_oso_pdm.proposal_management.review import Conflict, PanelReview, ReviewStatus

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
    expected = {
        "detail": "Duplicate prsl_id are not allowed: {'prsl-mvp01-20220923-00001'}"
    }
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
    expected = {"detail": "Proposal 'prsl-mvp01-20220923-00001' does not exist"}
    assert expected == result


def test_get_reviews_for_panel_with_wrong_id():
    panel_id = "wrong id"
    response = requests.get(f"{PHT_URL}/panels/reviews/{panel_id}")
    assert response.status_code == HTTPStatus.OK
    res = response.json()
    assert [] == res


def test_get_reviews_for_panel_with_valid_id():
    proposal = TestDataFactory.complete_proposal("my proposal")
    response = requests.post(
        f"{PHT_URL}/prsls/create", data=proposal.json(), headers=HEADERS
    )
    assert response.status_code == HTTPStatus.OK

    panel_id = "panel-test-20250717-00001"
    panel = TestDataFactory.panel_basic(panel_id=panel_id, name="New name")
    data = panel.json()
    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)
    assert response.status_code == HTTPStatus.OK

    conflict = Conflict(has_conflict=False, reason="")
    review = PanelReview(
        panel_id=panel_id,
        review_id="my review id",
        reviewer_id=REVIEWERS[0]["id"],
        prsl_id="my proposal",
        rank=5,
        conflict=conflict,
        status=ReviewStatus.DECIDED,
        submitted_by="Andrey",
    )
    response = requests.post(f"{PHT_URL}/reviews/", data=review.json(), headers=HEADERS)
    assert response.status_code == HTTPStatus.OK

    response = requests.get(f"{PHT_URL}/panels/reviews/{panel_id}")
    assert response.status_code == HTTPStatus.OK
    res = response.json()
    del res[0]["metadata"]
    expected = [
        {
            "panel_id": "panel-test-20250717-00001",
            "review_id": "my review id",
            "reviewer_id": "c8f8f18a-3c70-4c39-8ed9-2d8d180d99a1",
            "prsl_id": "my proposal",
            "rank": 5,
            "conflict": {"has_conflict": False, "reason": ""},
            "submitted_by": "Andrey",
            "status": "Decided",
        }
    ]
    assert expected == res


def test_get_list_panels_for_user():
    """
    Integration test:
    - Create multiple panels
    - Fetch created_by from one
    - Use GET /{user_id} to retrieve them
    - Ensure all created panels are returned
    """

    created_ids = []

    # Create 2 panels with unique panel_ids
    for i in range(2):
        panel_id = f"panel-test-{uuid.uuid4().hex[:8]}"
        panel = TestDataFactory.panel_basic(panel_id=panel_id, name=f"Star{i+1}")
        panel_json = panel.model_dump_json()

        response = requests.post(
            f"{PANELS_API_URL}",
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
    assert isinstance(panels, list), "Expected a list of panels"
    assert len(panels) >= 2, f"Expected at least 2 panels, got {len(panels)}"

    # Check that all created panels are returned
    returned_ids = {p["panel_id"] for p in panels}
    for panel_id in created_ids:
        assert panel_id in returned_ids, f"Missing panel {panel_id} in GET /{user_id}"
