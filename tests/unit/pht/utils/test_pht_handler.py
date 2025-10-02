from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from ska_oso_services.pht.service import proposal_service as svc
from ska_oso_services.pht.service.report_processing import (
    _get_array_class,
    join_proposals_panels_reviews_decisions,
)
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id
from tests.unit.util import REVIEWERS, TestDataFactory


def _to_iso_z(value):
    """Normalize submitted_on to 'YYYY-MM-DDTHH:MM:SSZ'"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raise TypeError(f"Unexpected submitted_on type: {type(value)}")


def _replace_investigators(proposal_info_obj, inv_objs):
    """Return a copy of `proposal_info_obj` with 'investigators' replaced (Pydantic v2)."""  # noqa: E501
    return proposal_info_obj.model_copy(update={"investigators": inv_objs})


def _parse_iso_z(s: str) -> datetime:
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' (or ISO with Z) into an aware UTC datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


class TestTransformUpdateProposal:
    @pytest.mark.parametrize(
        "case",
        [
            {
                "id": "submitted_by_sets_now",
                "submitted_by": "alice",
                "existing_submitted_on": None,
                "investigator_ids": ["u1", "u2"],
                "expected_status": "submitted",
                "expected_submitted_on": "NOW",
            },
            {
                "id": "draft_when_no_submit_fields",
                "submitted_by": None,
                "existing_submitted_on": None,
                "investigator_ids": [],
                "expected_status": "draft",
                "expected_submitted_on": None,
            },
        ],
        ids=lambda c: c["id"],
    )
    def test_transform_update_proposal(self, case):
        base = TestDataFactory.proposal()

        inv_factory = getattr(TestDataFactory, "investigator", None)
        inv_objs = (
            [inv_factory(user_id=i) for i in case["investigator_ids"]]
            if inv_factory
            else [SimpleNamespace(user_id=i) for i in case["investigator_ids"]]
        )

        new_info = _replace_investigators(base.proposal_info, inv_objs)

        incoming = base.model_copy(
            update={
                "submitted_by": case["submitted_by"],
                "submitted_on": case["existing_submitted_on"],
                "proposal_info": new_info,
            }
        )

        t0 = datetime.now(timezone.utc)
        out = svc.transform_update_proposal(incoming)
        t1 = datetime.now(timezone.utc)

        assert out.investigator_refs == case["investigator_ids"]

        # submitted_on logic
        if case["expected_submitted_on"] == "NOW":
            ts = _parse_iso_z(_to_iso_z(out.submitted_on))
            slack = timedelta(seconds=2)
            assert (t0 - slack) <= ts <= (t1 + slack), f"{ts=}, bounds=({t0}, {t1})"
        else:
            assert _to_iso_z(out.submitted_on) == case["expected_submitted_on"]

        status_str = str(out.status).lower().replace("proposalstatus.", "")
        assert status_str == case["expected_status"]

        assert out.prsl_id == incoming.prsl_id
        assert out.cycle == incoming.cycle
        assert out.proposal_info is incoming.proposal_info
        assert out.observation_info is incoming.observation_info


def test_join_proposals_panels_reviews_decisions():
    proposal1 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
    proposal2 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00002")
    panel = TestDataFactory.panel(
        reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
        panel_id="panel-test-20250616-00001",
        prsl_id_1=proposal1.prsl_id,
        prsl_id_2=proposal2.prsl_id,
    )
    decision = TestDataFactory.panel_decision(prsl_id=proposal1.prsl_id)
    reviews = TestDataFactory.reviews(
        prsl_id=proposal1.prsl_id,
        reviewer_id=REVIEWERS["sci_reviewers"][0]["id"],
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
            observation_info=SimpleNamespace(
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
            observation_info=SimpleNamespace(
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
            observation_info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=SimpleNamespace(array="Low")),
                    SimpleNamespace(array_details=SimpleNamespace(array="Mid")),
                ]
            )
        )
        assert _get_array_class(proposal) == "BOTH"

    def test_unknown_empty_obs(self):
        """Test when no observation sets are present"""
        proposal = SimpleNamespace(
            observation_info=SimpleNamespace(observation_sets=[])
        )
        assert _get_array_class(proposal) == "UNKNOWN"

    def test_unknown_none_array(self):
        """Test when array is None in observation set"""
        proposal = SimpleNamespace(
            observation_info=SimpleNamespace(
                observation_sets=[
                    SimpleNamespace(array_details=None),
                    SimpleNamespace(array_details=SimpleNamespace(array=None)),
                ]
            )
        )
        assert _get_array_class(proposal) == "UNKNOWN"

    def test_unknown_no_info(self):
        """Test with no info attribute in proposal"""
        proposal = SimpleNamespace(proposal_info=None, observation_info=None)
        assert _get_array_class(proposal) == "UNKNOWN"
