"""
Utility functions to be used in tests
"""
import json
import os.path

from deepdiff import DeepDiff


def assert_json_is_equal(json_a, json_b):
    """
    Utility function to compare two JSON objects
    """
    # key/values in the generated JSON do not necessarily have the same order
    # as the test string, even though they are equivalent JSON objects, e.g.,
    # subarray_id could be defined after dish. Ensure a stable test by
    # comparing the JSON objects themselves.

    # TODO: revisit sorted json
    obj_a = json.loads(json_a)
    obj_b = json.loads(json_b)

    sorted_obj_a = sorted(obj_a)
    sorted_obj_b = sorted(obj_b)

    try:
        assert sorted_obj_a == sorted_obj_b
    except AssertionError as exc:
        # raise a more useful exception that shows *where* the JSON differs
        diff = DeepDiff(sorted(obj_a), sorted(obj_b), ignore_order=True)
        raise AssertionError(f"JSON not equal: {diff}") from exc


def assert_json_is_equal_unsorted(json_a, json_b):
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
    except AssertionError as exc:
        # raise a more useful exception that shows *where* the JSON differs
        diff = DeepDiff(obj_a, obj_b, ignore_order=True)
        raise AssertionError(f"JSON not equal: {diff}") from exc


def load_string_from_file(filename):
    """
    Return a file from the current directory as a string
    """
    cwd, _ = os.path.split(__file__)
    path = os.path.join(cwd, filename)
    with open(path, "r", encoding="utf-8") as json_file:
        json_data = json_file.read()
        return json_data


VALID_PROPOSAL_DATA_JSON = load_string_from_file("testfile_sample_proposal.json")
VALID_PROPOSAL_FRONTEND_CREATE_JSON = load_string_from_file(
    "testfile_frontend_create_proposal.json"
)
VALID_PROPOSAL_FRONTEND_UPDATE_JSON = load_string_from_file(
    "testfile_frontend_update_proposal.json"
)
VALID_PROPOSAL_UPDATE_RESULT_JSON = load_string_from_file(
    "testfile_sample_edit_proposal_result.json"
)
VALID_PROPOSAL_GET_LIST_RESULT_JSON = load_string_from_file(
    "testfile_sample_get_list_proposal_result.json"
)
VALID_OSD_GET_OSD_CYCLE1_RESULT_JSON = load_string_from_file(
    "testfile_get_osd_cycle1.json"
)

VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_NO_TARGET_IN_RESULT = load_string_from_file(
    "testfile_sample_proposal_post_validation_body_no_target_in_result.json"
)

VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_OBS_SET_NO_TARGET = load_string_from_file(
    "testfile_sample_proposal_post_validation_body_obs_set_no_target.json"
)

VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_RESULT_NO_OBS = load_string_from_file(
    "testfile_sample_proposal_post_validation_body_result_no_obs.json"
)

VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_PASSING = load_string_from_file(
    "testfile_sample_proposal_post_validate_body_passing.json"
)

VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_NO_TARGET_IN_RESULT = load_string_from_file(
    "testfile_sample_proposal_post_validation_result_no_target_in_result.json"
)

VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_OBS_SET_NO_TARGET = load_string_from_file(
    "testfile_sample_proposal_post_validation_result_obs_set_no_target.json"
)

VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_RESULT_NO_OBS = load_string_from_file(
    "testfile_sample_proposal_post_validation_result_result_no_obs.json"
)

VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON = load_string_from_file(
    "testfile_sample_proposal_post_validate_result.json"
)

VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_PASSING = load_string_from_file(
    "testfile_sample_proposal_post_validate_result_passing.json"
)
