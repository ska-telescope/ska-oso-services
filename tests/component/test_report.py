from http import HTTPStatus

from ska_ser_skuid import EntityType, mint_skuid

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

HEADERS = {"Content-type": "application/json"}


def test_get_report_for_user(authrequests, test_panel_id):
    """
    Integration test for the GET /reports/ endpoint.
    """
    proposal1 = TestDataFactory.complete_proposal()
    proposal2 = TestDataFactory.complete_proposal()

    decision = TestDataFactory.panel_decision(prsl_id=proposal1.prsl_id, panel_id=test_panel_id)
    reviews = TestDataFactory.reviews(
        prsl_id=proposal1.prsl_id,
        reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
        review_id="rvw-tcomp01test",
        panel_id=test_panel_id,
    )

    prsl1_id = proposal1.prsl_id
    prsl2_id = proposal2.prsl_id
    panel_id = mint_skuid(EntityType.PNL)
    review_id = mint_skuid(EntityType.RVW)

    proposal1 = proposal1.model_copy(update={"prsl_id": prsl1_id})
    proposal2 = proposal2.model_copy(update={"prsl_id": prsl2_id})
    decision = decision.model_copy(update={"prsl_id": prsl1_id})
    reviews = reviews.model_copy(update={"prsl_id": prsl1_id, "review_id": review_id})

    panel = TestDataFactory.panel(
        reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
        panel_id=panel_id,
        prsl_id_1=prsl1_id,
        prsl_id_2=prsl2_id,
    )

    created_proposal1 = authrequests.post(
        f"{PHT_URL}/prsls/create", data=proposal1.model_dump_json(), headers=HEADERS
    )
    assert created_proposal1.status_code == HTTPStatus.OK, created_proposal1.text
    assert created_proposal1.json()["prsl_id"] == prsl1_id

    created_proposal2 = authrequests.post(
        f"{PHT_URL}/prsls/create", data=proposal2.model_dump_json(), headers=HEADERS
    )
    assert created_proposal2.status_code == HTTPStatus.OK, created_proposal2.text
    assert created_proposal2.json()["prsl_id"] == prsl2_id

    # --- Create panel, decision, review ---
    created_panel = authrequests.post(
        f"{PHT_URL}/panels/create", data=panel.model_dump_json(), headers=HEADERS
    )
    assert created_panel.status_code == HTTPStatus.OK, created_panel.text

    created_decision = authrequests.post(
        f"{PHT_URL}/panel/decision/create",
        data=decision.model_dump_json(),
        headers=HEADERS,
    )
    assert created_decision.status_code == HTTPStatus.OK, created_decision.text

    created_review = authrequests.post(
        f"{PHT_URL}/reviews/create", data=reviews.model_dump_json(), headers=HEADERS
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
