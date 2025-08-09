import pytest

from ska_oso_services.pht.service.panel_operations import (
    group_proposals_by_science_category,
)
from tests.unit.util import TestDataFactory


class TestGroupProposalsByScienceCategory:
    @pytest.mark.parametrize(
        ("panel_names", "proposals", "expected_ids_by_bucket", "expected_skipped"),
        [
            pytest.param(
                ["Cosmology", "Pulsars"],
                [
                    TestDataFactory.proposal_by_category(
                        "prsl-1", "Cosmology", info_as="dict"
                    ),
                    TestDataFactory.proposal_by_category(
                        "prsl-2", "Pulsars", info_as="obj"
                    ),
                ],
                {"Cosmology": ["prsl-1"], "Pulsars": ["prsl-2"]},
                0,
                id="basic-match-mixed-info",
            ),
            pytest.param(
                ["Cosmology"],
                [
                    TestDataFactory.proposal_by_category("prsl-1", "Cosmology"),
                    TestDataFactory.proposal_by_category(
                        "prsl-2", "Unknown"
                    ),  # skipped
                ],
                {"Cosmology": ["prsl-1"]},
                1,
                id="unmatched-gets-skipped",
            ),
            pytest.param(
                ["Cosmology"],
                [
                    TestDataFactory.proposal_by_category(
                        "prsl-1", None, info_as="dict"
                    ),  # dict missing key
                    TestDataFactory.proposal_by_category(
                        "prsl-2", None, info_as="obj"
                    ),  # obj None
                    TestDataFactory.proposal_by_category(
                        "prsl-3", None, info_as="none"
                    ),  # info None
                ],
                {"Cosmology": []},
                3,
                id="missing-info-or-category",
            ),
            pytest.param(
                ["Cosmology", "Pulsars"],
                [],
                {"Cosmology": [], "Pulsars": []},
                0,
                id="empty-inputs",
            ),
            pytest.param(
                [],
                [
                    TestDataFactory.proposal_by_category("prsl-1", "Cosmology"),
                    TestDataFactory.proposal_by_category("prsl-2", "Pulsars"),
                ],
                {},
                2,
                id="no-panel-names-skips-all",
            ),
        ],
    )
    def test_grouping_and_warnings(
        self, caplog, panel_names, proposals, expected_ids_by_bucket, expected_skipped
    ):
        with caplog.at_level("WARNING"):
            grouped = group_proposals_by_science_category(proposals, panel_names)

        assert set(grouped.keys()) == set(expected_ids_by_bucket.keys())

        for bucket, expected_ids in expected_ids_by_bucket.items():
            assert [p.prsl_id for p in grouped.get(bucket, [])] == expected_ids

        per_item = [r for r in caplog.records if "Skipping proposal" in r.message]
        summary = [r for r in caplog.records if "proposals skipped" in r.message]
        assert len(per_item) == expected_skipped
        assert len(summary) == (1 if expected_skipped else 0)

    @pytest.mark.parametrize(
        ("proposal", "expected_cat_repr"),
        [
            pytest.param(
                TestDataFactory.proposal_by_category("prsl-x", "Unknown"),
                "Unknown",
                id="unknown-string",
            ),
            pytest.param(
                TestDataFactory.proposal_by_category("prsl-y", None, info_as="dict"),
                "None",
                id="missing-dict-key",
            ),
            pytest.param(
                TestDataFactory.proposal_by_category("prsl-z", None, info_as="obj"),
                "None",
                id="none-on-obj",
            ),
        ],
    )
    def test_unmatched_warning_message_includes_details(
        self, caplog, proposal, expected_cat_repr
    ):
        with caplog.at_level("WARNING"):
            group_proposals_by_science_category([proposal], ["Cosmology"])

        msgs = [
            rec.message for rec in caplog.records if "Skipping proposal" in rec.message
        ]
        assert len(msgs) == 1
        assert proposal.prsl_id in msgs[0]
        assert expected_cat_repr in msgs[0]
