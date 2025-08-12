# tests/component/test_report.py
import uuid
from http import HTTPStatus

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

HEADERS = {"Content-type": "application/json"}


def test_get_report_for_user(authrequests):
    """
    Integration test for the GET /reports/ endpoint.
    """
    proposal1 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
    proposal2 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00002")

    decision = TestDataFactory.panel_decision(prsl_id=proposal1.prsl_id)
    reviews = TestDataFactory.reviews(
        prsl_id=proposal1.prsl_id,
        reviewer_id=REVIEWERS[0]["id"],
        review_id="rvw-mvp01-20220923-00001",
    )

    suffice = uuid.uuid4().hex[:6]
    prsl1_id = f"{proposal1.prsl_id}-{suffice}"
    prsl2_id = f"{proposal2.prsl_id}-{suffice}"
    panel_id = f"panel-test-20250616-00001-{suffice}"
    review_id = f"{reviews.review_id}-{suffice}"

    proposal1 = proposal1.model_copy(update={"prsl_id": prsl1_id})
    proposal2 = proposal2.model_copy(update={"prsl_id": prsl2_id})
    decision = decision.model_copy(update={"prsl_id": prsl1_id})
    reviews = reviews.model_copy(update={"prsl_id": prsl1_id, "review_id": review_id})

    panel = TestDataFactory.panel(
        reviewer_id=REVIEWERS[0]["id"],
        panel_id=panel_id,
        name="Test Panel",
        prsl_id_1=prsl1_id,
        prsl_id_2=prsl2_id,
    )

    created_proposal1 = authrequests.post(
        f"{PHT_URL}/prsls/create", data=proposal1.model_dump_json(), headers=HEADERS
    )
    assert created_proposal1.status_code == HTTPStatus.OK, created_proposal1.text
    assert created_proposal1.json() == prsl1_id

    created_proposal2 = authrequests.post(
        f"{PHT_URL}/prsls/create", data=proposal2.model_dump_json(), headers=HEADERS
    )
    assert created_proposal2.status_code == HTTPStatus.OK, created_proposal2.text
    assert created_proposal2.json() == prsl2_id

    # --- Create panel, decision, review ---
    created_panel = authrequests.post(
        f"{PHT_URL}/panels", data=panel.model_dump_json(), headers=HEADERS
    )
    assert created_panel.status_code == HTTPStatus.OK, created_panel.text

    created_decision = authrequests.post(
        f"{PHT_URL}/panel-decisions", data=decision.model_dump_json(), headers=HEADERS
    )
    assert created_decision.status_code == HTTPStatus.OK, created_decision.text

    created_review = authrequests.post(
        f"{PHT_URL}/reviews", data=reviews.model_dump_json(), headers=HEADERS
    )
    assert created_review.status_code == HTTPStatus.OK, created_review.text

    # --- GET report ---
    resp = authrequests.get(f"{PHT_URL}/report/")
    assert resp.status_code == HTTPStatus.OK, resp.text

    report = resp.json()
    assert isinstance(report, list) and len(report) > 0

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
        assert field in report[0], f"Missing field: {field}"
