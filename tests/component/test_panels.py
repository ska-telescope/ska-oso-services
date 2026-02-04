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
        panel = TestDataFactory.panel_basic(panel_id=panel_id, name=f"Star{i + 1}", cycle="2024A")
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


def test_generate_category_panels_multiple(authrequests):
    resp = authrequests.post(
        f"{PANELS_API_URL}/generate",
        params={"param": "Galaxy"},
    )
    assert resp.status_code == HTTPStatus.OK, resp.text

    data = resp.json()
    assert isinstance(data, dict)
    assert "created_count" in data and "created_names" in data

    created_count = data["created_count"]
    created_names = data["created_names"]

    assert isinstance(created_count, int)
    assert isinstance(created_names, list)
    assert all(isinstance(n, str) for n in created_names)
    assert len(created_names) == created_count
    assert len(set(created_names)) == len(created_names)

    assert created_count >= 0

    # Calling again should create nothing new
    resp2 = authrequests.post(
        f"{PANELS_API_URL}/generate",
        params={"param": "Galaxy"},
    )
    assert resp2.status_code == HTTPStatus.OK, resp2.text
    data2 = resp2.json()
    assert data2["created_count"] == 0
    assert data2["created_names"] == []


def test_generate_science_verification_panel(authrequests):
    resp = authrequests.post(
        f"{PANELS_API_URL}/generate",
        params={"param": "Science Verification"},
    )
    assert resp.status_code == HTTPStatus.OK, resp.text
    panel_id = resp.json()
    assert isinstance(panel_id, str), "Expected a single panel_id string for SV"
    assert panel_id.startswith("panel-")

    # Calling again should return the existing panel_id (no new creation)
    resp2 = authrequests.post(
        f"{PANELS_API_URL}/generate",
        params={"param": "Science Verification"},
    )
    assert resp2.status_code == HTTPStatus.OK, resp2.text
    assert resp2.json() == panel_id


def test_put_panel_with_proposal_and_reviewers(authrequests):
    # Create a proposal to reference in panel assignments
    proposal_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert proposal_response.status_code == HTTPStatus.OK, proposal_response.text
    prsl_id = proposal_response.json()["prsl_id"]

    # Create a panel to update
    panel_id = f"panel-test-put-{uuid.uuid4().hex[:8]}"
    panel = TestDataFactory.panel_basic(panel_id=panel_id, name="PutPanel", cycle="2024A")
    panel_response = authrequests.post(
        f"{PANELS_API_URL}/create",
        data=panel.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert panel_response.status_code == HTTPStatus.OK, panel_response.text
    created_panel_id = panel_response.json()

    sci_reviewer = TestDataFactory.reviewer_assignment(
        reviewer_id=f"sci-{uuid.uuid4().hex[:6]}",
        assigned_on="2025-06-16T11:23:01Z",
        status="Pending",
    )
    tech_reviewer = TestDataFactory.reviewer_assignment(
        reviewer_id=f"tech-{uuid.uuid4().hex[:6]}",
        assigned_on="2025-06-16T11:23:01Z",
        status="Pending",
    )
    proposal_assignment = TestDataFactory.proposal_assignment(
        prsl_id=prsl_id,
        assigned_on="2025-05-21T09:30:00Z",
    )

    panel_update = TestDataFactory.panel_with_assignment(
        panel_id=created_panel_id,
        name="PutPanel Updated",
        sci_reviewers=[sci_reviewer],
        tech_reviewers=[tech_reviewer],
        proposals=[proposal_assignment],
        cycle="2024A",
    )

    put_response = authrequests.put(
        f"{PANELS_API_URL}/{created_panel_id}",
        data=panel_update.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )

    assert put_response.status_code == HTTPStatus.OK, put_response.text
