"""
Component level tests for the /oda/configuration paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

from http import HTTPStatus

import pytest

from . import OSO_SERVICES_URL


@pytest.mark.parametrize(
    "identifier, reference_frame, expected_response",
    [
        (
            "47 Tuc",
            "equatorial",
            {
                "equatorial": {
                    "ra": "00:24:05.3590",
                    "dec": "-72:04:53.200",
                    "redshift": 0.0,
                    "velocity": -17.2,
                }
            },
        ),
        (
            "47 Tuc",
            "galactic",
            {
                "galactic": {
                    "lat": -44.8891135,
                    "lon": 305.8953327,
                    "redshift": 0.0,
                    "velocity": -17.2,
                }
            },
        ),
        (
            "M31",
            "equatorial",
            {
                "equatorial": {
                    "ra": "00:42:44.3300",
                    "dec": "41:16:07.500",
                    "redshift": 0.0,
                    "velocity": -300.0,
                }
            },
        ),
        (
            "N10",
            "galactic",
            {
                "galactic": {
                    "lat": -78.5856477,
                    "lon": 354.2101595,
                    "redshift": 0.0,
                    "velocity": 6800.0,
                }
            },
        ),
    ],
)
def test_coordinates_get(authrequests, identifier, reference_frame, expected_response):
    """
    Test that the GET /coordinates path receives the request
    and returns a success response with the resolved coordinates
    """

    response = authrequests.get(
        f"{OSO_SERVICES_URL}/coordinates/{identifier}/{reference_frame}"
    )

    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json()[reference_frame] == expected_response[reference_frame]
