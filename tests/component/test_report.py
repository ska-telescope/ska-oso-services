
import uuid
from http import HTTPStatus

import requests

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/report"
HEADERS = {"Content-type": "application/json"}


def test_get_report_for_user():
    """
    Integration test for the GET /reports/{user_id} endpoint.
    """

    user_id = "user-123"
    url = f"{PHT_URL}/report/{user_id}"

    response = requests.get(url)
    assert response.status_code == HTTPStatus.OK, response.text

    report = response.json()
    assert isinstance(report, list), f"Expected list, got {type(report)}"
    assert len(report) > 0, "Report should not be empty"

    # Check basic fields in the first report item
    item = report[0]
    required_fields = [
        "prsl_id", "title", "science_category", "proposal_status", "proposal_type",
        "cycle", "array", "panel_id", "panel_name"
    ]
    for field in required_fields:
        assert field in item, f"Missing field: {field}"

# def test_get_panel():
#     proposal1 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
#     proposal2 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00002")
#     panel = TestDataFactory.panel(
#         reviewer_id=REVIEWERS[0]["id"],
#         panel_id="panel-test-20250616-00001",
#         prsl_id_1=proposal1.prsl_id,
#         prsl_id_2=proposal2.prsl_id,
#     )
#     decision = TestDataFactory.panel_decision(prsl_id=proposal1.prsl_id)
#     reviews = TestDataFactory.reviews(
#         prsl_id=proposal1.prsl_id,
#         reviewer_id=REVIEWERS[0]["id"],
#         review_id="rvw-mvp01-20220923-00001",
#     )

#     get_response = requests.get(
#         f"{PHT_URL}/report",
#         data=VALID_NEW_PROPOSAL,
#         headers={"Content-Type": "application/json"},
#     )

#     rows = join_proposals_panels_reviews_decisions(
#         proposals=[proposal1, proposal2],
#         panels=[panel],
#         reviews=[reviews],
#         decisions=[decision],
#     )