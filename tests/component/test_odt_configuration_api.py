"""
Component level tests for the /oda/configuration paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

from http import HTTPStatus

from . import ODT_BASE_API_URL


def test_configuration_get(client):
    """
    Test that the GET /odt/configuration path receives the request
    and returns a success response
    """

    response = client.get(f"{ODT_BASE_API_URL}/configuration")
    assert response.status_code == HTTPStatus.OK, response.json()
