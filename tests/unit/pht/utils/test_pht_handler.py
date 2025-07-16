from types import SimpleNamespace

from ska_oso_services.pht.utils.pht_handler import (
    get_latest_entity_by_id,
    join_proposals_panels_reviews_decisions,
)
from tests.unit.util import REVIEWERS, TestDataFactory


def test_join_proposals_panels_reviews_decisions():
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

    rows = join_proposals_panels_reviews_decisions(
        proposals=[proposal1, proposal2],
        panels=[panel],
        reviews=[reviews],
        decisions=[decision],
    )

    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0].prsl_id == proposal1.prsl_id
    assert rows[0].panel_id == panel.panel_id
    assert rows[0].review_id == reviews.review_id
    assert rows[0].prsl_id == decision.prsl_id


def test_get_latest_entity_by_id():
    # Each entity is a SimpleNamespace with the needed fields
    entities = [
        SimpleNamespace(prsl_id="id1", metadata=SimpleNamespace(version=1)),
        SimpleNamespace(
            prsl_id="id1", metadata=SimpleNamespace(version=3)
        ),  # latest for id1
        SimpleNamespace(prsl_id="id1", metadata=SimpleNamespace(version=2)),
        SimpleNamespace(
            prsl_id="id2", metadata=SimpleNamespace(version=1)
        ),  # only one for id2
        SimpleNamespace(prsl_id="id3", metadata=SimpleNamespace(version=2)),
        SimpleNamespace(
            prsl_id="id3", metadata=SimpleNamespace(version=5)
        ),  # latest for id3
        SimpleNamespace(prsl_id="id3", metadata=SimpleNamespace(version=1)),
    ]

    result = get_latest_entity_by_id(entities, "prsl_id")
    result = sorted(result, key=lambda x: x.prsl_id)

    assert len(result) == 3
    assert any(e.prsl_id == "id1" and e.metadata.version == 3 for e in result)
    assert any(e.prsl_id == "id2" and e.metadata.version == 1 for e in result)
    assert any(e.prsl_id == "id3" and e.metadata.version == 5 for e in result)
