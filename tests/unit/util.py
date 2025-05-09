"""
Utility functions to be used in tests
"""

import json
import os.path
from datetime import datetime

from deepdiff import DeepDiff
from ska_db_oda.persistence.domain import set_identifier
from ska_oso_pdm.builders import low_imaging_sb, mid_imaging_sb
from ska_oso_pdm.project import Project
from ska_oso_pdm.proposal import Proposal
from ska_oso_pdm.sb_definition import SBDefinition, SBDefinitionID


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


def load_string_from_file(filename):
    """
    Return a file from the current directory as a string
    """
    cwd, _ = os.path.split(__file__)
    path = os.path.join(cwd, filename)
    with open(path, "r", encoding="utf-8") as json_file:
        json_data = json_file.read()
        return json_data


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
        prj = Project.model_validate_json(
            load_string_from_file("files/testfile_sample_project.json")
        )

        set_identifier(prj, prj_id)
        prj.metadata.version = version

        return prj

    @staticmethod
    def proposal(
        prsl_id: str = "prsl-mvp01-20220923-00001",
        
    ) -> Proposal:
        """
        Load a valid Proposal object from file and override prsl_id,
        or return invalid proposal dict if as_invalid is True.
        """

        proposal = Proposal.model_validate_json(
            load_string_from_file("files/create_proposal.json")
        )
        proposal.prsl_id = prsl_id

        return proposal


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
