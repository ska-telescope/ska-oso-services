"""
Component level tests for the /oda/prjs paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

import json

# pylint: disable=missing-timeout
from http import HTTPStatus

from ..unit.util import (
    VALID_PROJECT_WITHOUT_JSON,
    TestDataFactory,
    assert_json_is_equal,
)
from . import ODT_URL


def test_empty_sbd_created_and_linked_to_project(authrequests):
    """
    Test that an entity sent to POST /prjs creates an empty project, then a request
    to POST /prjs/<prj_id>/<obs_block_id>/sbds with an SBDefinition in the request body
    adds that SBDefinition to the Project
    """
    # Create an empty Project
    prj_post_response = authrequests.post(f"{ODT_URL}/prjs")

    assert prj_post_response.status_code == HTTPStatus.OK, prj_post_response.content
    prj_id = prj_post_response.json()["prj_id"]
    obs_block_id = prj_post_response.json()["obs_blocks"][0]["obs_block_id"]

    # Create an SBDefinition in that Project in the first observing block
    sbd_post_response = authrequests.post(
        f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/sbds",
        data=json.dumps({"telescope": "ska_mid"}),
        headers={"Content-type": "application/json"},
    )
    assert sbd_post_response.status_code == HTTPStatus.OK
    assert sbd_post_response.json()["sbd"]["telescope"] == "ska_mid"

    sbd_id = sbd_post_response.json()["sbd"]["sbd_id"]
    # Check the SBDefinition is linked to Project
    get_prj_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")
    assert get_prj_response.status_code == HTTPStatus.OK, get_prj_response.content
    assert get_prj_response.json()["obs_blocks"][0]["sbd_ids"][0] == sbd_id


def test_sbd_created_and_linked_to_project(authrequests):
    """
    Test that an entity sent to POST /prjs creates an empty project, then a request
    to POST /prjs/<prj_id>/<obs_block_id>/sbds without a request body adds
    an empty SBDefinition to that Project
    """
    # Create an empty Project
    prj_post_response = authrequests.post(
        f"{ODT_URL}/prjs",
        headers={"Content-type": "application/json"},
    )

    assert prj_post_response.status_code == HTTPStatus.OK, prj_post_response.content
    prj_id = prj_post_response.json()["prj_id"]
    obs_block_id = prj_post_response.json()["obs_blocks"][0]["obs_block_id"]

    # Create an SBDefinition in that Project in the first observing block
    sbd_post_response = authrequests.post(
        f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/sbds",
        data=json.dumps({"telescope": "ska_mid"}),
        headers={"Content-type": "application/json"},
    )
    assert sbd_post_response.status_code == HTTPStatus.OK, sbd_post_response.content
    sbd_id = sbd_post_response.json()["sbd"]["sbd_id"]

    # Check the SBDefinition is linked to Project
    get_prj_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")
    assert get_prj_response.status_code == HTTPStatus.OK, get_prj_response.content
    assert get_prj_response.json()["obs_blocks"][0]["sbd_ids"][0] == sbd_id


def test_prj_post_then_get(authrequests):
    """
    Test that an entity sent to POST /prjs can then be retrieved
    with GET /prjs/{identifier}
    """
    post_response = authrequests.post(
        f"{ODT_URL}/prjs",
        data=VALID_PROJECT_WITHOUT_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )

    prj_id = post_response.json()["prj_id"]
    get_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")

    # Assert the ODT can get the Project, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    assert_json_is_equal(
        get_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )


def test_prj_post_then_put(authrequests):
    """
    Test that an entity sent to POST /prjs can then be
    updated with PUT /prjs/{identifier}
    """
    post_response = authrequests.post(
        f"{ODT_URL}/prjs",
        data=VALID_PROJECT_WITHOUT_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )

    prj_id = post_response.json()["prj_id"]
    prj_to_update = TestDataFactory.project(prj_id=prj_id).model_dump_json()
    put_response = authrequests.put(
        f"{ODT_URL}/prjs/{prj_id}",
        data=prj_to_update,
        headers={"Content-type": "application/json"},
    )
    # Assert the ODT can get the Project, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert put_response.status_code == HTTPStatus.OK, put_response.content
    assert_json_is_equal(
        put_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )
    assert put_response.json()["metadata"]["version"] == 2


def test_prj_get_not_found(authrequests):
    """
    Test that the GET /prjs/{identifier} path returns
    404 when the Project is not found in the ODA
    """

    response = authrequests.get(f"{ODT_URL}/prjs/123")

    assert response.status_code == HTTPStatus.NOT_FOUND, response.content
    assert response.json() == {
        "detail": "The requested identifier 123 could not be found.",
    }


def test_prj_put_not_found(authrequests):
    """
    Test that the GET /prjs/{identifier} path returns
    404 when the Project is not found in the ODA
    """

    response = authrequests.get(f"{ODT_URL}/prjs/123")

    assert response.status_code == HTTPStatus.NOT_FOUND, response.content
    assert response.json() == {
        "detail": "The requested identifier 123 could not be found.",
    }
