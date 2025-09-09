import uuid
from http import HTTPStatus

from ..unit.util import TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/panels"
HEADERS = {"Content-type": "application/json"}


def test_get_list_panels_for_user(authrequests):
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
        panel = TestDataFactory.panel_basic(
            panel_id=panel_id, name=f"Star{i+1}", cycle="2024A"
        )
        panel_json = panel.model_dump_json()

        response = authrequests.post(
            f"{PANELS_API_URL}/create",
            data=panel_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json())

    # Get created_by from one of the created panels
    example_panel_id = created_ids[0]
    get_response = authrequests.get(f"{PANELS_API_URL}/{example_panel_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content

    list_response = authrequests.get(f"{PANELS_API_URL}/")
    assert list_response.status_code == HTTPStatus.OK, list_response.content

    panels = list_response.json()
    assert isinstance(panels, list), "Expected a list of panels"
    assert len(panels) >= 2, f"Expected at least 2 panels, got {len(panels)}"

    # Check that all created panels are returned
    returned_ids = {p["panel_id"] for p in panels}
    for panel_id in created_ids:
        assert panel_id in returned_ids, f"Missing panel {panel_id}"


def test_auto_create_category_panels(authrequests):
    payload = {
        "name": "Galaxy",
        "sci_reviewers": [],
        "tech_reviewers": [],
        "proposals": [],
    }

    response = authrequests.post(
        f"{PANELS_API_URL}/auto-create",
        json=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert isinstance(result, list), "Expected a list of panels"

    # At least one category must be present
    panel_names = [panel["name"] for panel in result]
    assert "Cosmology" in panel_names
    assert all("panel_id" in panel for panel in result)
    assert all("proposal_count" in panel for panel in result)


def test_auto_create_science_verification_panel(authrequests):
    payload = {
        "name": "Science Verification",
        "sci_reviewers": [],
        "tech_reviewers": [],
        "proposals": [],
    }

    response = authrequests.post(
        f"{PANELS_API_URL}/auto-create",
        json=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    panel_id = response.json()
    assert isinstance(panel_id, str), "Expected a single panel_id string for SV"
    assert panel_id.startswith("panel-")
