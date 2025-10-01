from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from ska_oso_services.common.error_handling import BadRequestError, ODANotFound
from ska_oso_services.pht.api import panels as panels_api  # for ProposalStatus enum
from ska_oso_services.pht.api.panels import ensure_submitted_proposals_under_review
from ska_oso_services.pht.service import panel_operations as panel_ops
from ska_oso_services.pht.service.panel_operations import (
    group_proposals_by_science_category,assign_to_existing_panel
)
from tests.unit.util import TestDataFactory


def _ns(**kw):
    return SimpleNamespace(**kw)


class TestAssignToExistingPanel:
    def test_adds_only_new_proposals_and_overwrites_reviewers(self):
        existing_assignment = _ns(prsl_id="prop-1")
        panel = _ns(
            panel_id="panel-1",
            name="Cosmology",
            proposals=[existing_assignment], 
            sci_reviewers=["old-sci"],
            tech_reviewers=["old-tech"],
        )

        # incoming proposals: one duplicate, two new, and one invalid
        p_dup = _ns(prsl_id="prop-1")
        p_new1 = _ns(prsl_id="prop-2")
        p_new2 = _ns(prsl_id="prop-3")
        p_invalid = _ns()  # no prsl_id → ignored

        uow = mock.MagicMock()
        auth = _ns(user_id="user-123")

        persisted_panel = _ns(
            panel_id="panel-1",
            name="Cosmology",
            proposals=[],
            sci_reviewers=["sci-1"],
            tech_reviewers=["tec-1"],
        )
        uow.panels.add.return_value = persisted_panel

        persisted, added_count, added_ids = assign_to_existing_panel(
            uow=uow,
            auth=auth,
            panel=panel,
            proposals=[p_dup, p_new1, p_new2, p_invalid],
            sci_reviewers=["sci-1"],
            tech_reviewers=["tec-1"],
        )

        assert persisted is persisted_panel
        assert added_count == 2
        assert set(added_ids) == {"prop-2", "prop-3"}

        # Panel mutation 
        assert panel.sci_reviewers == ["sci-1"]
        assert panel.tech_reviewers == ["tec-1"]
        # proposals now include the existing + 2 new assignments
        prsl_ids_after = [getattr(x, "prsl_id", None) for x in (panel.proposals or [])]
        assert prsl_ids_after.count("prop-1") == 1
        assert "prop-2" in prsl_ids_after
        assert "prop-3" in prsl_ids_after

        # Persisted once with correct args
        uow.panels.add.assert_called_once()
        args, kwargs = uow.panels.add.call_args
        assert args[0] is panel
        assert args[1] == auth.user_id

    def test_none_reviewers_leave_as_is(self):
        panel = _ns(
            panel_id="panel-2",
            name="Stars",
            proposals=[],
            sci_reviewers=["keep-sci"],
            tech_reviewers=["keep-tech"],
        )
        uow = mock.MagicMock()
        auth = _ns(user_id="user-123")
        uow.panels.add.return_value = panel 

        persisted, added_count, added_ids = assign_to_existing_panel(
            uow=uow,
            auth=auth,
            panel=panel,
            proposals=[],  # nothing to add
            sci_reviewers=None, 
            tech_reviewers=None, 
        )

        assert persisted is panel
        assert added_count == 0
        assert added_ids == []
        assert panel.sci_reviewers == ["keep-sci"]
        assert panel.tech_reviewers == ["keep-tech"]
        uow.panels.add.assert_called_once_with(panel, auth.user_id)

    def test_empty_lists_clear_reviewers(self):
        panel = _ns(
            panel_id="panel-3",
            name="Transients",
            proposals=[],
            sci_reviewers=["will-be-cleared"],
            tech_reviewers=["will-be-cleared"],
        )
        uow = mock.MagicMock()
        auth = _ns(user_id="user-123")
        uow.panels.add.return_value = panel

        persisted, added_count, added_ids = assign_to_existing_panel(
            uow=uow,
            auth=auth,
            panel=panel,
            proposals=[],  
            sci_reviewers=[],  
            tech_reviewers=[],  
        )

        assert persisted is panel
        assert added_count == 0
        assert added_ids == []
        assert panel.sci_reviewers == []  
        assert panel.tech_reviewers == []  
        uow.panels.add.assert_called_once_with(panel, auth.user_id)

    def test_skips_already_assigned_ids(self):
        panel = _ns(
            panel_id="panel-4",
            name="Galaxy",
            proposals=[_ns(prsl_id="p1"), _ns(prsl_id="p2")],
            sci_reviewers=[],
            tech_reviewers=[],
        )
        uow = mock.MagicMock()
        auth = _ns(user_id="user-123")
        uow.panels.add.return_value = panel

        persisted, added_count, added_ids = assign_to_existing_panel(
            uow=uow,
            auth=auth,
            panel=panel,
            proposals=[_ns(prsl_id="p1"), _ns(prsl_id="p2")],  
            sci_reviewers=None,
            tech_reviewers=None,
        )

        assert persisted is panel
        assert added_count == 0
        assert added_ids == []

        prsl_ids_after = [getattr(x, "prsl_id", None) for x in (panel.proposals or [])]
        assert prsl_ids_after == ["p1", "p2"]
        uow.panels.add.assert_called_once_with(panel, auth.user_id)

    def test_handles_none_proposals_gracefully(self):
        panel = _ns(
            panel_id="panel-5",
            name="Dust",
            proposals=None,  
            sci_reviewers=[],
            tech_reviewers=[],
        )
        uow = mock.MagicMock()
        auth = _ns(user_id="user-123")
        uow.panels.add.return_value = panel

        persisted, added_count, added_ids = assign_to_existing_panel(
            uow=uow,
            auth=auth,
            panel=panel,
            proposals=None, 
            sci_reviewers=None,
            tech_reviewers=None,
        )

        assert persisted is panel
        assert added_count == 0
        assert added_ids == []
        uow.panels.add.assert_called_once_with(panel, auth.user_id)


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
                    TestDataFactory.proposal_by_category("prsl-2", "Unknown"),
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
                    ),
                    TestDataFactory.proposal_by_category("prsl-2", None, info_as="obj"),
                    TestDataFactory.proposal_by_category(
                        "prsl-3", None, info_as="none"
                    ),
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


class TestEnsureSubmittedProposalsUnderReview:
    def test_sets_under_review_and_dedupes_ids(self):
        """SUBMITTED -> UNDER_REVIEW; duplicates processed once; blanks ignored."""
        uow = mock.MagicMock()
        auth = SimpleNamespace(user_id="test_user")

        p1 = SimpleNamespace(
            prsl_id="prop-1",
            status=panels_api.ProposalStatus.SUBMITTED,
            user=auth.user_id,
        )
        p2 = SimpleNamespace(
            prsl_id="prop-2",
            status=panels_api.ProposalStatus.UNDER_REVIEW,
            user=auth.user_id,
        )

        # Only two unique lookups despite duplicate 'prop-1'
        uow.prsls.get.side_effect = [p1, p2]

        ensure_submitted_proposals_under_review(
            uow, auth, ["  prop-1  ", "prop-2", "prop-1", "", "   "]
        )

        # Lookups only for unique, non-blank IDs in order of first occurrence
        assert [c.args[0] for c in uow.prsls.get.call_args_list] == ["prop-1", "prop-2"]

        # Only the SUBMITTED proposal is written back with new status
        assert p1.status == panels_api.ProposalStatus.UNDER_REVIEW
        uow.prsls.add.assert_called_once_with(p1, auth.user_id)

    def test_skips_when_already_under_review(self):
        """When proposal already UNDER_REVIEW."""
        uow = mock.MagicMock()
        p = SimpleNamespace(
            prsl_id="prop-ur", status=panels_api.ProposalStatus.UNDER_REVIEW
        )
        uow.prsls.get.return_value = p
        user = "test_user"
        ensure_submitted_proposals_under_review(uow, user, ["prop-ur"])

        uow.prsls.add.assert_not_called()
        uow.prsls.get.assert_called_once_with("prop-ur")

    def test_ignores_blank_ids_entirely(self):
        """Blank/whitespace IDs are ignored (no repo calls)."""
        uow = mock.MagicMock()
        user = "test_user"

        ensure_submitted_proposals_under_review(uow, user, ["", "   ", "\n", "\t"])

        uow.prsls.get.assert_not_called()
        uow.prsls.add.assert_not_called()
