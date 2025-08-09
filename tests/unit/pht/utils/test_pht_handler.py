from types import SimpleNamespace

from ska_oso_services.pht.utils.pht_helper import (
    get_latest_entity_by_id
)
from ska_oso_services.pht.service.report_processing import join_proposals_panels_reviews_decisions,   _get_array_class
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
    # Use SimpleNamespace with the needed fields for each mocked proposal with metadata
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
    assert any(obj.prsl_id == "id1" and obj.metadata.version == 3 for obj in result)
    assert any(obj.prsl_id == "id2" and obj.metadata.version == 1 for obj in result)
    assert any(obj.prsl_id == "id3" and obj.metadata.version == 5 for obj in result)


class TestGetArrayClass:
    def test_low_only(self):
        """Test when only Low array is present"""
        proposal = SimpleNamespace(
            info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=SimpleNamespace(array="Low")),
                    SimpleNamespace(array_details=SimpleNamespace(array="LOW-EXTRA")),
                ]
            )
        )
        assert _get_array_class(proposal) == "LOW"

    def test_mid_only(self):
        """Test when only Mid array is present"""
        proposal = SimpleNamespace(
            info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=SimpleNamespace(array="Mid")),
                    SimpleNamespace(array_details=SimpleNamespace(array="MID-OTHER")),
                ]
            )
        )
        assert _get_array_class(proposal) == "MID"

    def test_both_arrays(self):
        """Test when both Low and Mid arrays are present"""
        proposal = SimpleNamespace(
            info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=SimpleNamespace(array="Low")),
                    SimpleNamespace(array_details=SimpleNamespace(array="Mid")),
                ]
            )
        )
        assert _get_array_class(proposal) == "BOTH"

    def test_unknown_empty_obs(self):
        """Test when no observation sets are present"""
        proposal = SimpleNamespace(info=SimpleNamespace(observation_sets=[]))
        assert _get_array_class(proposal) == "UNKNOWN"

    def test_unknown_none_array(self):
        """Test when array is None in observation set"""
        proposal = SimpleNamespace(
            info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=None),
                    SimpleNamespace(array_details=SimpleNamespace(array=None)),
                ]
            )
        )
        assert _get_array_class(proposal) == "UNKNOWN"

    def test_unknown_no_info(self):
        """Test with no info attribute in proposal"""
        proposal = SimpleNamespace(info=None)
        assert _get_array_class(proposal) == "UNKNOWN"
