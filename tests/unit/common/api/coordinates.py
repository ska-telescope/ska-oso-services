from http import HTTPStatus

import pytest

from tests.unit.conftest import APP_BASE_API_URL

COORDINATES_API_URL = f"{APP_BASE_API_URL}/coordinates"


@pytest.mark.parametrize(
    "identifier,reference_frame,expected_response",
    [
        (
            "M31",
            "equatorial",
            {
                "equatorial": {
                    "ra": "00:42:44.330",
                    "dec": "+41:16:07.500",
                    "redshift": -0.0010006922855944561,
                    "velocity": -300.0,
                }
            },
        ),
        (
            "N10",
            "galactic",
            {
                "galactic": {
                    "lat": -78.5856,
                    "lon": 354.21,
                    "redshift": 0.022945539640067736,
                    "velocity": 6800.0,
                }
            },
        ),
        (
            "N10",
            "equatorial",
            {
                "equatorial": {
                    "dec": "-33:51:30.197",
                    "ra": "00:08:34.539",
                    "redshift": 0.022945539640067736,
                    "velocity": 6800.0,
                }
            },
        ),
    ],
)
def test_get_coordinates(client, identifier, reference_frame, expected_response):

    response = client.get(f"{COORDINATES_API_URL}/{identifier}/{reference_frame}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == expected_response


def test_get_coordinates_without_valid_reference_frame_returns(client):
    response = client.get(f"{COORDINATES_API_URL}/M31/unsupported-frame")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Input should be 'equatorial' or 'galactic'" in response.text
