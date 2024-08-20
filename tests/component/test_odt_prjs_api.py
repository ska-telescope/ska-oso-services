"""
Component level tests for ska-oso-ost-services.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-ost-services in the same cluster
"""

import json

# pylint: disable=missing-timeout
from http import HTTPStatus

import requests

from ..unit.util import (
    VALID_PROJECT_WITHOUT_JSON,
    TestDataFactory,
    assert_json_is_equal,
)
from . import ODT_URL


def test_sbd_created_and_linked_to_project():
    """
    Test that an entity sent to POST /prjs creates an empty project, then a request
    to POST /prjs/<prj_id>/<obs_block_id>/sbds adds an SBDefinition to that Project
    """
    # Create an empty Project
    prj_post_response = requests.post(
        f"{ODT_URL}/prjs",
        data=json.dumps({"telescope": "ska_mid"}),
        headers={"Content-type": "application/json"},
    )

    assert prj_post_response.status_code == HTTPStatus.OK, prj_post_response.content
    prj_id = prj_post_response.json()["prj_id"]

    # Create an SBDefinition in that Project in the first observing block
    sbd_post_response = requests.post(
        f"{ODT_URL}/prjs/{prj_id}/ob-1/sbds",
    )
    assert sbd_post_response.status_code == HTTPStatus.OK
    sbd_id = sbd_post_response.json()["sbd"]["sbd_id"]

    # Check the SBDefinition is linked to Project
    get_prj_response = requests.get(f"{ODT_URL}/prjs/{prj_id}")
    assert get_prj_response.status_code == HTTPStatus.OK
    assert get_prj_response.json()["obs_blocks"][0]["sbd_ids"][0] == sbd_id


def test_prj_post_then_get():
    """
    Test that an entity sent to POST /prjs can then be retrieved
    with GET /prjs/{identifier}
    """
    post_response = requests.post(
        f"{ODT_URL}/prjs",
        data=VALID_PROJECT_WITHOUT_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        post_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )

    prj_id = post_response.json()["prj_id"]
    get_response = requests.get(f"{ODT_URL}/prjs/{prj_id}")

    # Assert the ODT can get the Project, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        get_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )


def test_prj_post_then_put():
    """
    Test that an entity sent to POST /prjs can then be
    updated with PUT /prjs/{identifier}
    """
    post_response = requests.post(
        f"{ODT_URL}/prjs",
        data=VALID_PROJECT_WITHOUT_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        post_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )

    prj_id = post_response.json()["prj_id"]
    prj_to_update = TestDataFactory.project(prj_id=prj_id).model_dump_json()
    put_response = requests.put(
        f"{ODT_URL}/prjs/{prj_id}",
        data=prj_to_update,
        headers={"Content-type": "application/json"},
    )
    # Assert the ODT can get the Project, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert put_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        put_response.content,
        VALID_PROJECT_WITHOUT_JSON,
        exclude_paths=["root['metadata']", "root['prj_id']"],
    )
    assert put_response.json()["metadata"]["version"] == 2


def test_prj_get_not_found():
    """
    Test that the GET /prjs/{identifier} path returns
    404 when the Project is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/prjs/123")

    assert response.json() == {
        "status": HTTPStatus.NOT_FOUND,
        "title": "Not Found",
        "detail": "Identifier 123 not found in repository",
        "traceback": None,
    }
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_prj_put_not_found():
    """
    Test that the GET /prjs/{identifier} path returns
    404 when the Project is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/prjs/123")

    assert response.json() == {
        "status": HTTPStatus.NOT_FOUND,
        "title": "Not Found",
        "detail": "Identifier 123 not found in repository",
        "traceback": None,
    }
    assert response.status_code == HTTPStatus.NOT_FOUND
