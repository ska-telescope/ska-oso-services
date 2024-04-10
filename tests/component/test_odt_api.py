"""
Component level tests for ska-oso-ost-services.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-ost-services in the same cluster
"""
# pylint: disable=missing-timeout
import json
import os
from http import HTTPStatus
from importlib.metadata import version

import pytest
import requests

from ska_oso_services.odt import codec as mcodec

from ..unit.util import (
    CODEC,
    SBDEFINITION_WITHOUT_ID_OR_METADATA_JSON,
    VALID_MID_SBDEFINITION_JSON,
    TestDataFactory,
    assert_json_is_equal,
)

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
ODT_URL = os.getenv(
    "ODT_URL",
    "http://ska-oso-services-rest-test:5000"
    f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}",
)


def test_sbd_create():
    """
    Test that the GET /sbds/create path receives the request
    and returns a valid SBD
    """

    response = requests.get(f"{ODT_URL}/sbds/create")
    assert response.status_code == HTTPStatus.OK

    sbd = mcodec.decode(json.dumps(response.json()))
    assert sbd.interface


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
    assert result["messages"] == []


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

    assert post_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        post_response.content,
        VALID_MID_SBDEFINITION_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    get_response = requests.get(f"{ODT_URL}/sbds/{sbd_id}")

    # Assert the ODT can get the SBD, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert get_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        get_response.content,
        VALID_MID_SBDEFINITION_JSON,
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

    assert post_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        post_response.content,
        VALID_MID_SBDEFINITION_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )

    sbd_id = post_response.json()["sbd_id"]
    sbd_to_update = CODEC.dumps(TestDataFactory.sbdefinition(sbd_id=sbd_id))
    put_response = requests.put(
        f"{ODT_URL}/sbds/{sbd_id}",
        data=sbd_to_update,
        headers={"Content-type": "application/json"},
    )
    # Assert the ODT can get the SBD, ignoring the metadata as it contains
    # timestamps and is the responsibility of the ODA
    assert put_response.status_code == HTTPStatus.OK
    assert_json_is_equal(
        put_response.content,
        VALID_MID_SBDEFINITION_JSON,
        exclude_paths=["root['metadata']", "root['sbd_id']"],
    )
    assert put_response.json()["metadata"]["version"] == 2


def test_sbd_get_not_found():
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/sbds/123")

    assert response.json() == {
        "status": HTTPStatus.NOT_FOUND,
        "title": "Not Found",
        "detail": "SBDefinition with identifier 123 not found in repository",
    }
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_sbd_put_not_found():
    """
    Test that the GET /sbds/{identifier} path returns
    404 when the SBD is not found in the ODA
    """

    response = requests.get(f"{ODT_URL}/sbds/123")

    assert response.json() == {
        "status": HTTPStatus.NOT_FOUND,
        "title": "Not Found",
        "detail": "SBDefinition with identifier 123 not found in repository",
    }
    assert response.status_code == HTTPStatus.NOT_FOUND


# TODO temporarily disable until OpenAPI validation fixed #pylint: disable=fixme
# def test_sbd_post_validation_error():
#     """
#     Test that the POST /sbds/{identifier} path returns the correct error response
#     when an invalid SBDefinition is sent
#     """
#
#     response = requests.post(
#         f"{ODT_URL}/sbds/sbd-mvp01-20200325-00001",
#         data=INVALID_MID_SBDEFINITION_JSON,
#         headers={"Content-type": "application/json"},
#     )
#
#     assert response.status_code == HTTPStatus.BAD_REQUEST
#
#     result = json.loads(response.content)
#
#     assert result["title"] == "Bad Request"
#     assert result["detail"] == "'telescope' is a required property"
