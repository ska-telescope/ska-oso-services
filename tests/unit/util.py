"""
Utility functions to be used in tests
"""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from deepdiff import DeepDiff
from ska_db_oda.persistence.domain import set_identifier
from ska_oso_pdm.builders import low_imaging_sb, mid_imaging_sb
from ska_oso_pdm.project import Project
from ska_oso_pdm.proposal import Proposal
from ska_oso_pdm.proposal.proposal_access import ProposalAccess
from ska_oso_pdm.proposal_management import PanelDecision, PanelReview
from ska_oso_pdm.proposal_management.panel import Panel
from ska_oso_pdm.sb_definition import SBDefinition, SBDefinitionID

# from ska_oso_services.pht.model import (
#     ProposalAccessByProposalResponse,
#     ProposalAccessResponse,
# )

CUR_DIR = Path(__file__).parent


def assert_json_is_equal(json_a, json_b, exclude_paths=None):
    """
    Utility function to compare two JSON objects
    """
    # key/values in the generated JSON do not necessarily have the same order
    # as the test string, even though they are equivalent JSON objects, e.g.,
    # subarray_id could be defined after dish. Ensure a stable test by
    # comparing the JSON objects themselves.
    obj_a = json.loads(json_a)
    obj_b = json.loads(json_b)
    try:
        assert obj_a == obj_b
    except AssertionError:
        # raise a more useful exception that shows *where* the JSON differs
        diff = DeepDiff(obj_a, obj_b, ignore_order=True, exclude_paths=exclude_paths)
        assert {} == diff, f"JSON not equal: {diff}"


def load_string_from_file(filename: str, directory: str = "files") -> str:
    """
    Return a file from the current directory as a string
    """
    path = CUR_DIR / directory / filename
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
        return data


class TestDataFactory:
    @staticmethod
    def sbdefinition(
        sbd_id: SBDefinitionID = "sbd-mvp01-20200325-00001",
        version: int = 1,
        created_on: datetime = datetime.fromisoformat(
            "2022-03-28T15:43:53.971548+00:00"
        ),
        without_metadata: bool = False,
    ) -> SBDefinition:
        sbd = mid_imaging_sb()
        set_identifier(sbd, sbd_id)

        if without_metadata:
            sbd.metadata = None
            return sbd

        sbd.metadata.version = version
        sbd.metadata.created_on = created_on

        return sbd

    @staticmethod
    def lowsbdefinition(
        sbd_id: SBDefinitionID = "sbd-mvp01-20200325-00001",
        version: int = 1,
        created_on: datetime = datetime.fromisoformat(
            "2022-03-28T15:43:53.971548+00:00"
        ),
        without_metadata: bool = False,
    ) -> SBDefinition:
        sbd = low_imaging_sb()
        set_identifier(sbd, sbd_id)

        if without_metadata:
            sbd.metadata = None
            return sbd

        sbd.metadata.version = version
        sbd.metadata.created_on = created_on

        return sbd

    @staticmethod
    def project(
        prj_id: str = "prj-mvp01-20220923-00001",
        version: int = 1,
    ) -> Project:

        data = load_string_from_file("project.json")
        prj = Project.model_validate_json(data)

        set_identifier(prj, prj_id)
        prj.metadata.version = version

        return prj

    @staticmethod
    def project_with_two_mid_observation_groups(
        prj_id: str | None = "prj-mvp01-20220923-00001",
        version: int = 1,
    ) -> Project:

        data = load_string_from_file("project_with_mid_observation_set.json")
        prj = Project.model_validate_json(data)

        set_identifier(prj, prj_id)
        prj.metadata.version = version

        return prj

    @staticmethod
    def project_with_two_low_targets(
        prj_id: str | None = "prj-mvp01-20220923-00001",
        version: int = 1,
    ) -> Project:

        data = load_string_from_file("project_with_low_observation_set.json")
        prj = Project.model_validate_json(data)

        set_identifier(prj, prj_id)
        prj.metadata.version = version

        return prj

    @staticmethod
    def reviews(
        panel_id: str = "panel-test-20250717-00001",
        review_id: str = "rvw-mvp01-20220923-00001",
        prsl_id: str = "prsl-mvp01-20220923-00001",
        reviewer_id="string",
    ) -> PanelReview:
        """
        Load a valid proposal review object from file and override review_id,
        """

        data = load_string_from_file("panel_review.json")
        review = PanelReview.model_validate_json(data)
        review.panel_id = panel_id
        review.review_id = review_id
        review.prsl_id = prsl_id
        review.reviewer_id = reviewer_id

        return review

    @staticmethod
    def panel_decision(
        decision_id: str = "pnld-mvp01-20220923-00001",
        prsl_id: str = "prsl-mvp01-20220923-00001",
    ) -> PanelDecision:
        """
        Load a valid proposal panel decision object from file and override decision_id,
        """

        data = load_string_from_file("panel_decision.json")
        decision = PanelDecision.model_validate_json(data)
        decision.decision_id = decision_id
        decision.prsl_id = prsl_id

        return decision

    @staticmethod
    def proposal(prsl_id: str = "prsl-mvp01-20220923-00001") -> Proposal:
        """
        Load a valid Proposal object from file and override prsl_id,
        """

        data = load_string_from_file("create_proposal.json")
        proposal = Proposal.model_validate_json(data)
        proposal.prsl_id = prsl_id

        return proposal

    @staticmethod
    def panel_basic(panel_id: str = None, name: str = None) -> Panel:
        data = {
            "panel_id": panel_id,
            "name": name,
            "reviewers": [],
            "proposals": [],
        }
        panel = Panel.model_validate_json(json.dumps(data))
        set_identifier(panel, panel_id)

        return panel

    @staticmethod
    def panel(
        panel_id: str = "panel-test-20250616-00002",
        name: str = "Stargazers",
        reviewer_id="rev-001",
        prsl_id_1="prsl-mvp01-20220923-00001",
        prsl_id_2="prsl-mvp01-20220923-00002",
    ) -> Panel:
        data = {
            "panel_id": "panel-Galactic-2025.2",
            "name": name,
            "proposals": [
                {"prsl_id": prsl_id_1, "assigned_on": "2025-05-21T09:30:00Z"},
                {"prsl_id": prsl_id_2, "assigned_on": "2025-05-21T09:45:00Z"},
            ],
            "reviewers": [
                {
                    "reviewer_id": reviewer_id,
                    "assigned_on": "2025-06-16T11:23:01Z",
                    "status": "Pending",
                }
            ],
        }
        panel = Panel.model_validate_json(json.dumps(data))
        set_identifier(panel, panel_id)

        return panel

    @staticmethod
    def complete_proposal(
        prsl_id: str = "prsl-mvp01-20220923-00001", status="draft"
    ) -> Proposal:
        filename = "complete_proposal.json"
        data = load_string_from_file(filename)
        prsl = Proposal.model_validate_json(data)
        prsl.prsl_id = prsl_id
        prsl.status = status
        return prsl

    @staticmethod
    def proposal_report(
        prsl_id: str = "prsl-mvp01-20220923-00001",
        panel_id: str = "panel-test-20250616-00001",
        reviewer_id: str = "rev-001",
        review_id: str = "rvw-mvp01-20220923-00001",
    ):
        data = {
            "prsl_id": prsl_id,
            "panel_id": panel_id,
            "reviewer_id": reviewer_id,
            "review_id": review_id,
            "science_category": "Imaging",
            "proposal_status": "Accepted",
            "proposal_type": "Large",
            "array": "Mid",
            "proposal_attributes": ["coordinated_proposal"],
            "cycle": "2025-2",
            "title": "The Milky Way View",
            "recommendation": "Accept",
        }

        return data

    @staticmethod
    def proposal_access(
        access_id: str = "prsl-mvp01-20220923-00001",
        prsl_id: str = "panel-test-20250616-00001",
        user_id: str = "rev-001",
        role: str = "Principal Investigator",
        permission: list[str] = None,
    ) -> ProposalAccess:
        if permission is None:
            permission = ["view"]

        data = {
            "access_id": access_id,
            "prsl_id": prsl_id,
            "user_id": user_id,
            "role": role,
            "permissions": permission,
        }

        proposal_access = ProposalAccess.model_validate_json(json.dumps(data))
        set_identifier(proposal_access, access_id)

        return proposal_access

    @staticmethod
    def proposal_access_response(
        prsl_id: str,
        access_id: str = "access_id1",
        user_id: str = "user1",
        role: str = "Principal Investigator",
        permission: list[str] = None,
    ) -> ProposalAccess:

        if permission is None:
            permission = ["view"]

        data = {
            "prsl_id": prsl_id,
            "access_id": access_id,
            "user_id": user_id,
            "role": role,
            "permissions": permission,
        }

        proposal_access_response = ProposalAccess.model_validate_json(json.dumps(data))

        return proposal_access_response

    @staticmethod
    def email_payload(email="test@example.com", prsl_id="SKAO123"):
        return {"email": email, "prsl_id": prsl_id}

    @staticmethod
    def proposal_by_category(prsl_id, science_category, *, info_as="dict"):
        """Module-level helper so it’s usable inside @parametrize."""
        if info_as == "dict":
            info = (
                {}
                if science_category is None
                else {"science_category": science_category}
            )
        elif info_as == "obj":
            info = SimpleNamespace(science_category=science_category)
        else:
            info = None
        return SimpleNamespace(prsl_id=prsl_id, info=info)


VALID_MID_SBDEFINITION_JSON = TestDataFactory.sbdefinition().model_dump_json()
VALID_LOW_SBDEFINITION_JSON = TestDataFactory.lowsbdefinition().model_dump_json()
SBDEFINITION_WITHOUT_ID_JSON = TestDataFactory.sbdefinition(
    sbd_id=None
).model_dump_json()
SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON = TestDataFactory.sbdefinition(
    sbd_id=None, without_metadata=True
).model_dump_json()

VALID_PROJECT_WITHOUT_JSON = TestDataFactory.project(prj_id=None).model_dump_json()

# proposal entry
VALID_NEW_PROPOSAL = TestDataFactory.proposal().model_dump_json()
VALID_REVIEW = TestDataFactory.reviews().model_dump_json()
VALID_PANEL_DECISION = TestDataFactory.panel_decision().model_dump_json()
PAYLOAD_SUCCESS = TestDataFactory.email_payload()
PAYLOAD_CONNECT_FAIL = TestDataFactory.email_payload(
    "connectfail@example.com", "PRSL999"
)
PAYLOAD_BAD_TO = TestDataFactory.email_payload("badto@example.com", "PRSLBAD")
PAYLOAD_GENERIC_FAIL = TestDataFactory.email_payload(
    "genericfail@example.com", "GENERICFAIL"
)
REVIEWERS = json.loads(load_string_from_file("get_reviewers.json"))
