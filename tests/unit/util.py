"""
Utility functions to be used in tests
"""

import json
from datetime import datetime
from pathlib import Path

from deepdiff import DeepDiff
from ska_db_oda.persistence.domain import set_identifier
from ska_oso_pdm.builders import low_imaging_sb, mid_imaging_sb
from ska_oso_pdm.project import Project
from ska_oso_pdm.proposal import Proposal
from ska_oso_pdm.proposal_management.panel import Panel
from ska_oso_pdm.sb_definition import SBDefinition, SBDefinitionID

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
    def proposal(prsl_id: str = "prsl-mvp01-20220923-00001") -> Proposal:
        """
        Load a valid Proposal object from file and override prsl_id,
        """

        data = load_string_from_file("create_proposal.json")
        proposal = Proposal.model_validate_json(data)
        proposal.prsl_id = prsl_id

        return proposal

    @staticmethod
    def panel_basic(
        panel_id: str = "panel-test-20250616-00001",
        name: str = "Stargazers",
    ) -> Panel:
        data = {"panel_id": "panel-Galactic-2025", "name": name}
        panel = Panel.model_validate_json(json.dumps(data))
        set_identifier(panel, panel_id)

        return panel

    @staticmethod
    def panel(
        panel_id: str = "panel-test-20250616-00002",
        name: str = "Stargazers",
        reviewer_id="rev-001",
    ) -> Panel:
        data = {
            "panel_id": "panel-Galactic-2025.2",
            "name": name,
            "proposals": [
                {"prsl_id": "prop-astro-01", "assigned_on": "2025-05-21T09:30:00Z"},
                {"prsl_id": "prop-astro-02", "assigned_on": "2025-05-21T09:45:00Z"},
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
    def complete_proposal():
        filename = "complete_proposal.json"
        data = load_string_from_file(filename)
        p = Proposal.model_validate_json(data)
        return p

    @staticmethod
    def email_payload(email="test@example.com", prsl_id="SKAO123"):
        return {"email": email, "prsl_id": prsl_id}


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
PAYLOAD_SUCCESS = TestDataFactory.email_payload()
PAYLOAD_CONNECT_FAIL = TestDataFactory.email_payload(
    "connectfail@example.com", "PRSL999"
)
PAYLOAD_BAD_TO = TestDataFactory.email_payload("badto@example.com", "PRSLBAD")
PAYLOAD_GENERIC_FAIL = TestDataFactory.email_payload(
    "genericfail@example.com", "GENERICFAIL"
)
REVIEWERS = json.loads(load_string_from_file("get_reviewers.json"))
