"""
Component level tests for the /oda/sbds paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making reqfuests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
from http import HTTPStatus

import pytest

from ..unit.util import TestDataFactory, assert_json_is_equal
from . import ODT_URL


def test_sbd_create(authrequests):
    """
    Test that the GET /sbds/create path receives the request
    and returns a valid SBD
    """

    response = authrequests.get(f"{ODT_URL}/sbds/create")
    assert response.status_code == HTTPStatus.OK

    assert response.json()["interface"] == "https://schema.skao.int/ska-oso-pdm-sbd/0.1"


def test_post_without_ob_ref_fails(authrequests):
    response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=TestDataFactory.sbdefinition(sbd_id=None, ob_ref="not an ob").model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    result = response.json()

    assert result["detail"] == "The referenced identifier not an ob could not be found"


@pytest.mark.xray("XTP-34548")
def test_sbd_post_then_get(authrequests, test_project):
    """
    Test that an entity POSTed to /sbds can then be retrieved
    with GET /sbds/{identifier}
    """
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=test_project.obs_blocks[0].obs_block_id)
    post_response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        sbd.model_dump_json(),
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")

    # Assert the ODT can get the SBD, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    assert_json_is_equal(
        get_response.content,
        sbd.model_dump_json(),
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )


def test_sbd_status_get(authrequests, test_project):
    """
    Test that GET /sbds/{identifier}/status returns a current Status
    for an existing SBD.
    """
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=test_project.obs_blocks[0].obs_block_id)
    post_response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content

    sbd_id = post_response.json()["sbd_id"]
    status_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}/status")

    assert status_response.status_code == HTTPStatus.OK, status_response.content
    assert status_response.json()["status"] == "Draft"


def test_sbd_status_update(authrequests, test_project):
    """
    Test that PUT /sbds/{identifier}/status updates the status of the SBD.
    """
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=test_project.obs_blocks[0].obs_block_id)
    post_response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content

    sbd_id = post_response.json()["sbd_id"]
    put_response = authrequests.put(f"{ODT_URL}/sbds/{sbd_id}/status")

    assert put_response.status_code == HTTPStatus.OK, put_response.content
    assert put_response.json()["status"] == "Ready"


def test_sbd_post_then_put(authrequests, test_project):
    """
    Test that an entity POSTed to /sbds can then be updated with PUT /sbds/{identifier}
    """
    ob_ref = test_project.obs_blocks[0].obs_block_id
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=ob_ref)

    post_response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        sbd.model_dump_json(),
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    sbd_to_update = TestDataFactory.sbdefinition(sbd_id=sbd_id, ob_ref=ob_ref).model_dump_json()
    put_response = authrequests.put(
        f"{ODT_URL}/sbds/{sbd_id}",
        data=sbd_to_update,
        headers={"Content-type": "application/json"},
    )
    # Assert the ODT can get the SBD, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert put_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        put_response.content,
        sbd_to_update,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )
    assert put_response.json()["metadata"]["version"] == 2


def test_sbd_get_not_found(authrequests):
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = authrequests.get(f"{ODT_URL}/sbds/123")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "The requested identifier 123 could not be found."


def test_sbd_put_not_found(authrequests):
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = authrequests.get(f"{ODT_URL}/sbds/123")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "The requested identifier 123 could not be found."


def test_sbd_put_validation_error(authrequests):
    """
    Test that the PUT /sbds/{identifier} path with an invalid SBDefinition
    returns a FastAPI generated validation error response
    """

    response = authrequests.put(
        f"{ODT_URL}/sbds/sbd-mvp01-20200325-00001",
        data="""{"telescope": "not_a_telescope"}""",
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    result = response.json()

    assert result["detail"][0]["msg"] == "Input should be 'ska_mid', 'ska_low' or 'MeerKAT'"


def test_sbd_delete_success(authrequests, test_project):
    """
    Test that DELETE /sbds/{identifier} removes the SBD and returns 204 No Content.
    """
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=test_project.obs_blocks[0].obs_block_id)
    post_response = authrequests.post(
        f"{ODT_URL}/sbds",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    sbd_id = post_response.json()["sbd_id"]

    delete_response = authrequests.delete(f"{ODT_URL}/sbds/{sbd_id}")
    assert delete_response.status_code == HTTPStatus.NO_CONTENT, delete_response.content

    get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
    assert get_response.status_code == HTTPStatus.NOT_FOUND


def test_sbd_delete_not_found(authrequests):
    """
    Test that DELETE /sbds/{identifier} returns 404 if SBD not found.
    """
    bad_sbd_id = "not-a-sbd"
    delete_response = authrequests.delete(f"{ODT_URL}/sbds/{bad_sbd_id}")
    assert delete_response.status_code == HTTPStatus.NOT_FOUND

    assert "The requested identifier could not be found" in delete_response.json()["detail"]
