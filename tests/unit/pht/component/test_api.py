import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from os import getenv

import pytest
import requests

# TODO: add assert_json_is_equal
from ..unit.util import (
    VALID_PROPOSAL_DATA_JSON,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_NO_TARGET_IN_RESULT,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_OBS_SET_NO_TARGET,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_PASSING,
    VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_RESULT_NO_OBS,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_NO_TARGET_IN_RESULT,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_OBS_SET_NO_TARGET,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_PASSING,
    VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_RESULT_NO_OBS,
    assert_json_is_equal_unsorted,
)

# TODO: revisit test_proposal_put
# from ska_oso_pht_services.connectors.pht_handler import transform_update_proposal

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-pht-services")
PHT_URL = getenv(
    "PHT_URL", f"http://ska-oso-pht-services-rest-test:5000/{KUBE_NAMESPACE}/pht/api/v2"
)

test_prsl_id = ""


# TODO: revisit test cases
def test_proposal_create():
    """
    Test that the POST /proposals path receives the request
    and returns a valid Proposal ID
    """

    global test_prsl_id  # pylint: disable=W0603

    response = requests.post(
        f"{PHT_URL}/proposals",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    curTime = datetime.today().strftime("%Y%m%d")
    assert f"prsl-t0001-{curTime}" in response.text
    assert response.status_code == HTTPStatus.OK

    test_prsl_id = response.text


def test_proposal_get():
    """
    Test that the GET /proposals/{identifier} path receives the request
    and returns the correct response of the created proposal
    """

    response = requests.get(f"{PHT_URL}/proposals/{test_prsl_id}")
    result = json.loads(response.content)

    assert result["prsl_id"] == test_prsl_id
    assert response.status_code == HTTPStatus.OK


def test_proposal_get_list():
    """
    Test that the GET /proposals/list/{identifier} path receives the request
    and returns the correct response in an array
    """

    requests.post(
        f"{PHT_URL}/proposals",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    response = requests.get(f"{PHT_URL}/proposals/list/DefaultUser")
    result = json.loads(response.content)

    assert response.status_code == HTTPStatus.OK
    assert result[0]["metadata"]["created_by"] == "DefaultUser"


def test_proposal_put():
    """
    TODO: review pdm for datatype for investigators and investigator_id
    Test that the PUT /proposals/{identifier} path receives the request
    and returns the correct response
    """

    NEW_VALID_PROPOSAL_DATA_JSON = VALID_PROPOSAL_DATA_JSON

    new_valid_proposal_data_json = json.loads(NEW_VALID_PROPOSAL_DATA_JSON)
    new_valid_proposal_data_json["prsl_id"] = test_prsl_id

    NEW_VALID_PROPOSAL_DATA_JSON = json.dumps(new_valid_proposal_data_json)

    response = requests.put(
        f"{PHT_URL}/proposals/{test_prsl_id}",
        data=NEW_VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK

    before_transform = json.loads(response.content)

    assert before_transform["metadata"]["version"] == 2
    assert datetime.fromisoformat(
        before_transform["metadata"]["last_modified_on"].replace("Z", "+00:00")
    ).timestamp() == pytest.approx(
        datetime.now(timezone.utc).timestamp(),
        abs=timedelta(seconds=100).total_seconds(),
    )

    # expected = transform_update_proposal(json.loads(VALID_PROPOSAL_DATA_JSON))
    # result = transform_update_proposal(json.loads(response.content))

    # TODO: review pdm for datatype for investigators and investigator_id
    # assert expected == result


def test_proposal_validate_no_target_in_result():
    """
    Test that the POST /proposals/validate path receives the request
    and returns result and messages for no target in result case
    """

    response = requests.post(
        f"{PHT_URL}/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_NO_TARGET_IN_RESULT,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_NO_TARGET_IN_RESULT
    )


def test_proposal_validate_obs_set_no_target():
    """
    Test that the POST /proposals/validate path receives the request
    and returns result and messages for obs set no target case
    """

    response = requests.post(
        f"{PHT_URL}/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_OBS_SET_NO_TARGET,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_OBS_SET_NO_TARGET
    )


def test_proposal_validate_result_no_obs():
    """
    Test that the POST /proposals/validate path receives the request
    and returns result and messages for result no obs case
    """

    response = requests.post(
        f"{PHT_URL}/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_RESULT_NO_OBS,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_RESULT_NO_OBS
    )


def test_proposal_validate_result_sample_proposal():
    """
    Test that the POST /proposals/validate path receives the request
    and returns result and messages for using sample proposal case
    """

    response = requests.post(
        f"{PHT_URL}/proposals/validate",
        data=VALID_PROPOSAL_DATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON
    )


def test_proposal_validate_passing():
    """
    Test that the POST /proposals/validate path receives the request
    and returns result and messages for passing case
    """

    response = requests.post(
        f"{PHT_URL}/proposals/validate",
        data=VALID_PROPOSAL_POST_VALIDATE_BODY_JSON_PASSING,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert_json_is_equal_unsorted(
        response.text, VALID_PROPOSAL_POST_VALIDATE_RESULT_JSON_PASSING
    )
