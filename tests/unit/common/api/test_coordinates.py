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
                    "ra": "00:42:44.3300",
                    "dec": "+41:16:07.500",
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
                    "lat": -78.5856,
                    "lon": 354.21,
                    "redshift": 0.0,
                    "velocity": 6800.0,
                }
            },
        ),
        (
            "N10",
            "equatorial",
            {
                "equatorial": {
                    "ra": "00:08:34.5389",
                    "dec": "-33:51:30.197",
                    "redshift": 0.0,
                    "velocity": 6800.0,
                }
            },
        ),
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
            "HL Tau",
            "equatorial",
            {
                "equatorial": {
                    "ra": "04:31:38.5108",
                    "dec": "+18:13:57.860",
                    "redshift": 0.0,
                    "velocity": 0.0,
                }
            },
        ),
        (
            "WISEA J035950.64+670741.5",
            "equatorial",
            {
                "equatorial": {
                    "ra": "03:59:50.6448",
                    "dec": "+67:07:41.592",
                    "redshift": 0.0,
                    "velocity": 0.0,
                }
            },
        ),
        (
            "CR7",
            "equatorial",
            {
                "equatorial": {
                    "ra": "10:00:58.0008",
                    "dec": "+01:48:15.156",
                    "redshift": 6.541,
                    "velocity": 0.0,
                }
            },
        ),
    ],
)
def test_get_coordinates(client, identifier, reference_frame, expected_response):

    response = client.get(f"{COORDINATES_API_URL}/{identifier}/{reference_frame}")
    assert response.status_code == HTTPStatus.OK, response.json()
    assert response.json() == expected_response


def test_get_coordinates_notfound(client):

    expected_response = {"detail": "Object not found in SIMBAD or NED"}
    response = client.get(f"{COORDINATES_API_URL}/NOSOURCE/equatorial")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == expected_response


def test_get_coordinates_without_valid_reference_frame_returns(client):
    response = client.get(f"{COORDINATES_API_URL}/M31/unsupported-frame")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Input should be 'equatorial' or 'galactic'" in response.text
