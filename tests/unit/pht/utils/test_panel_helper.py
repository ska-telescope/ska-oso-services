from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from ska_oso_services.pht.service import panel_operations as panel_ops
from ska_oso_services.pht.service.panel_operations import (
    group_proposals_by_science_category,
)
from tests.unit.util import TestDataFactory


def _prsl_id(item):
    return item["prsl_id"] if isinstance(item, dict) else getattr(item, "prsl_id")


def _assigned_on(item):
    return (
        item["assigned_on"] if isinstance(item, dict) else getattr(item, "assigned_on")
    )


def _with_proposals(panel: Any, proposals_as_dicts: list[dict]) -> Any:
    """Return a copy of `panel` with proposals replaced ."""

    return panel.model_copy(update={"proposals": proposals_as_dicts})


class TestUpsertPanel:
    @pytest.mark.parametrize(
        "case",
        [
            {
                "id": "existing_appends_only_new",
                "existing": True,
                "existing_ids": ["A"],
                "incoming_ids": ["A", "B"],
                "sci_reviewers": [],
                "tech_reviewers": [],
                "expect_add_called": False,
                "expect_final_ids": ["A", "B"],
            },
            {
                "id": "existing_no_incoming",
                "existing": True,
                "existing_ids": ["A", "B"],
                "incoming_ids": [],
                "sci_reviewers": [],
                "tech_reviewers": [],
                "expect_add_called": False,
                "expect_final_ids": ["A", "B"],
            },
            {
                "id": "create_with_two",
                "existing": False,
                "existing_ids": [],
                "incoming_ids": ["A", "B"],
                "sci_reviewers": [],
                "tech_reviewers": [],
                "expect_add_called": True,
                "expect_final_ids": ["A", "B"],
            },
            {
                "id": "create_empty",
                "existing": False,
                "existing_ids": [],
                "incoming_ids": [],
                "sci_reviewers": [],
                "tech_reviewers": [],
                "expect_add_called": True,
                "expect_final_ids": [],
            },
        ],
        ids=lambda c: c["id"],
    )
    def test_upsert_panel_parametrized(self, monkeypatch, case):
        fixed_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(
            panel_ops,
            "datetime",
            SimpleNamespace(now=lambda tz: fixed_now),
            raising=True,
        )

        uow = mock.MagicMock()

        incoming = [SimpleNamespace(prsl_id=pid) for pid in case["incoming_ids"]]

        if case["existing"]:
            existing_panel = TestDataFactory.panel(
                name="SomePanel", reviewer_id="test_id"
            )

            existing_dicts = [
                {"prsl_id": pid, "assigned_on": fixed_now - timedelta(minutes=5)}
                for pid in case["existing_ids"]
            ]
            existing_panel = _with_proposals(existing_panel, existing_dicts)

            monkeypatch.setattr(
                panel_ops,
                "get_latest_entity_by_id",
                lambda _q, _k: [existing_panel],
                raising=True,
            )
        else:
            monkeypatch.setattr(
                panel_ops, "get_latest_entity_by_id", lambda _q, _k: [], raising=True
            )
            monkeypatch.setattr(
                panel_ops,
                "generate_entity_id",
                lambda prefix: f"{prefix}-new-123",
                raising=True,
            )
            # Echo saved panel back from repo
            uow.panels.add.side_effect = lambda p: p

        result = panel_ops.upsert_panel(
            uow=uow,
            panel_name="SomePanel",
            sci_reviewers=case["sci_reviewers"],
            tech_reviewers=case["tech_reviewers"],
            proposal_list=incoming,
        )

        if case["expect_add_called"]:
            uow.panels.add.assert_called_once()
            added_panel = uow.panels.add.call_args[0][0]
            assert added_panel.name == "SomePanel"
            assert [_prsl_id(p) for p in added_panel.proposals] == case[
                "expect_final_ids"
            ]
            assert added_panel.sci_reviewers == case["sci_reviewers"]
            assert added_panel.tech_reviewers == case["tech_reviewers"]
        else:
            uow.panels.add.assert_not_called()

        final_ids = [_prsl_id(p) for p in result.proposals]
        assert final_ids == case["expect_final_ids"]

        appended_ids = set(case["incoming_ids"]) - set(case["existing_ids"])
        if appended_ids:
            stamped = {
                _prsl_id(p) for p in result.proposals if _assigned_on(p) == fixed_now
            }
            assert appended_ids.issubset(stamped)


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
