"""
Component level tests for the /oda/configuration paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

from http import HTTPStatus

import requests

from . import BASE_API_URL


def test_coordinates_get():
    """
    Test that the GET /coordinates path receives the request
    and returns a success response with the resolved coordinates
    """

    response = requests.get(f"{BASE_API_URL}/coordinates/N10/equatorial")
    expected_response = {
        "equatorial": {
            "dec": "-33:51:30.197",
            "ra": "00:08:34.539",
            "redshift": 0.022945539640067736,
            "velocity": 6800.0,
        }
    }
    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == expected_response
