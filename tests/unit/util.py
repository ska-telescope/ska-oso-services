"""
Utility functions to be used in tests
"""
import json
import os.path
from typing import Optional

from deepdiff import DeepDiff
from ska_oso_pdm.entities.common.sb_definition import SBDefinition, SBDefinitionID
from ska_oso_pdm.schemas import CODEC


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


VALID_MID_SBDEFINITION_JSON = load_string_from_file("odt/testfile_sample_mid_sb.json")
valid_mid_sbdefinition = CODEC.loads(SBDefinition, VALID_MID_SBDEFINITION_JSON)

INVALID_MID_SBDEFINITION_JSON = CODEC.dumps(
    SBDefinition(sbd_id="sbi-mvp01-20200325-00001")
)


def sbdefinition(
    sbd_id: Optional[SBDefinitionID] = "sbi-mvp01-20200325-00001",
    version: Optional[int] = None,
) -> SBDefinition:
    sbd = CODEC.loads(SBDefinition, VALID_MID_SBDEFINITION_JSON)
    sbd.sbd_id = sbd_id
    if version:
        sbd.metadata.version = version

    return sbd


def sbdefinition_without_metadata(
    sbd_id: Optional[SBDefinitionID] = "sbi-mvp01-20200325-00001",
) -> SBDefinition:
    sbd = CODEC.loads(SBDefinition, VALID_MID_SBDEFINITION_JSON)
    sbd.sbd_id = sbd_id
    sbd.metadata = None
    return sbd


sbd_without_id = CODEC.dumps(sbdefinition(sbd_id=None))
sbd_without_id_or_metadata = CODEC.dumps(sbdefinition_without_metadata(sbd_id=None))
