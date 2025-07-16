# tests/component/test_report.py
from http import HTTPStatus

import requests

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

HEADERS = {"Content-type": "application/json"}


def test_get_report_for_user():
    """
    Integration test for the GET /reports/{user_id} endpoint.
    """

    proposal1 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
    proposal2 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00002")
    panel = TestDataFactory.panel(
        reviewer_id=REVIEWERS[0]["id"],
        panel_id="panel-test-20250616-00001",
        prsl_id_1=proposal1.prsl_id,
        prsl_id_2=proposal2.prsl_id,
    )
    decision = TestDataFactory.panel_decision(prsl_id=proposal1.prsl_id)
    reviews = TestDataFactory.reviews(
        prsl_id=proposal1.prsl_id,
        reviewer_id=REVIEWERS[0]["id"],
        review_id="rvw-mvp01-20220923-00001",
    )

    created_proposal1 = requests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal1.json(),
        headers=HEADERS,
    )
    assert created_proposal1.status_code == HTTPStatus.OK, created_proposal1.text

    created_proposal2 = requests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal2.json(),
        headers=HEADERS,
    )
    assert created_proposal2.status_code == HTTPStatus.OK, created_proposal2.text

    created_panel = requests.post(
        f"{PHT_URL}/panels",
        data=panel.json(),
        headers=HEADERS,
    )
    assert created_panel.status_code == HTTPStatus.OK, created_panel.text

    created_decision = requests.post(
        f"{PHT_URL}/panel-decisions",
        data=decision.json(),
        headers=HEADERS,
    )
    assert created_decision.status_code == HTTPStatus.OK, created_decision.text

    created_review = requests.post(
        f"{PHT_URL}/reviews",
        data=reviews.json(),
        headers=HEADERS,
    )
    assert created_review.status_code == HTTPStatus.OK, created_review.text

    user_id = "DefaultUser"  # Use a fixed user ID for testing
    url = f"{PHT_URL}/report/{user_id}"

    response = requests.get(url)
    assert response.status_code == HTTPStatus.OK, response.text

    report = response.json()
    assert isinstance(report, list), f"Expected list, got {type(report)}"
    assert len(report) > 0, "Report should not be empty"

    # Check basic fields in the  first report item
    item = report[0]
    required_fields = [
        "prsl_id",
        "title",
        "science_category",
        "proposal_status",
        "proposal_type",
        "cycle",
        "array",
        "panel_id",
        "panel_name",
    ]
    for field in required_fields:
        assert field in item, f"Missing field: {field}"
