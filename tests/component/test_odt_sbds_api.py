"""
Component level tests for the /oda/sbds paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
import json
from http import HTTPStatus

import pytest
import requests

from ..unit.util import (
    SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
    VALID_MID_SBDEFINITION_JSON,
    TestDataFactory,
    assert_json_is_equal,
)
from . import ODT_URL


def test_sbd_create():
    """
    Test that the GET /sbds/create path receives the request
    and returns a valid SBD
    """

    response = requests.get(f"{ODT_URL}/sbds/create")
    assert response.status_code == HTTPStatus.OK

    assert response.json()["interface"] == "https://schema.skao.int/ska-oso-pdm-sbd/0.1"


def test_sbd_validate():
    """
    Test that the POST /sbds/validate path receives the request
    and returns the correct response
    """

    response = requests.post(
        f"{ODT_URL}/sbds/validate",
        data=VALID_MID_SBDEFINITION_JSON,
        headers={"Content-type": "application/json"},
    )

    result = json.loads(response.content)
    assert result["valid"]
    assert result["messages"] == {}


@pytest.mark.xray("XTP-34548")
def test_sbd_post_then_get():
    """
    Test that an entity POSTed to /sbds can then be retrieved
    with GET /sbds/{identifier}
    """
    post_response = requests.post(
        f"{ODT_URL}/sbds",
        data=SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    get_response = requests.get(f"{ODT_URL}/sbds/{sbd_id}")

    # Assert the ODT can get the SBD, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    assert_json_is_equal(
        get_response.content,
        SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )


def test_sbd_post_then_put():
    """
    Test that an entity POSTed to /sbds can then be updated with PUT /sbds/{identifier}
    """
    post_response = requests.post(
        f"{ODT_URL}/sbds",
        data=SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
        headers={"Content-type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK, post_response.content
    assert_json_is_equal(
        post_response.content,
        SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    sbd_to_update = TestDataFactory.sbdefinition(sbd_id=sbd_id).model_dump_json()
    put_response = requests.put(
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


def test_sbd_get_not_found():
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/sbds/123")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "detail": "Identifier 123 not found in repository",
    }


def test_sbd_put_not_found():
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/sbds/123")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "detail": "Identifier 123 not found in repository",
    }


def test_sbd_put_validation_error():
    """
    Test that the PUT /sbds/{identifier} path with an invalid SBDefinition
    returns a FastAPI generated validation error response
    """

    response = requests.put(
        f"{ODT_URL}/sbds/sbd-mvp01-20200325-00001",
        data="""{"telescope": "not_a_telescope"}""",
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    result = response.json()

    assert (
        result["detail"][0]["msg"]
        == "Input should be 'ska_mid', 'ska_low' or 'MeerKAT'"
    )
