"""
Component level tests for the /oda/configuration paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

from http import HTTPStatus

import requests

from . import ODT_URL


def test_configuration_get():
    """
    Test that the GET /odt/configuration path receives the request
    and returns a success response
    """

    response = requests.get(f"{ODT_URL}/sbds/create")
    assert response.status_code == HTTPStatus.OK
