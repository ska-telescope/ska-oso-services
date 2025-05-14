import json
from http import HTTPStatus
from unittest import mock

import pytest

from ska_oso_services.common.coordinateslookup import Equatorial
from ska_oso_services.common.error_handling import NotFoundError
from tests.unit.conftest import APP_BASE_API_URL
from tests.unit.util import assert_json_is_equal

COORDINATES_API_URL = f"{APP_BASE_API_URL}/coordinates"

#Define test cases
COORDINATE_TEST_CASES = [
    (
        "M31",
        "equatorial",
        Equatorial(
            ra="00:42:44.3300",
            dec="+41:16:07.500",
            velocity=-300.0,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="00:08:34.5389",
            dec="-33:51:30.197",
            velocity=6800.0,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="00:08:34.5389",
            dec="-33:51:30.197",
            velocity=6800.0,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="00:24:05.3590",
            dec="-72:04:53.200",
            velocity=-17.2,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="04:31:38.5108",
            dec="+18:13:57.860",
            velocity=0.0,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="03:59:50.6448",
            dec="+67:07:41.592",
            velocity=0.0,
            redshift=0.0,
        ),
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
        Equatorial(
            ra="10:00:58.0008",
            dec="+01:48:15.156",
            velocity=0.0,
            redshift=6.541,
        ),
        {
            "equatorial": {
                "ra": "10:00:58.0008",
                "dec": "+01:48:15.156",
                "redshift": 6.541,
                "velocity": 0.0,
            }
        },
    ),
]


class TestCoordinates:
    @pytest.mark.parametrize(
        "identifier, reference_frame, mock_return, expected_response",
        COORDINATE_TEST_CASES,
    )
    @mock.patch("ska_oso_services.common.api.coordinates.get_coordinates")
    def test_success(
        self,
        mock_get_coordinates,
        identifier,
        reference_frame,
        mock_return,
        expected_response,
        client,
    ):
        """
        Test successful coordinate lookups
        """
        mock_get_coordinates.return_value = mock_return

        response = client.get(f"{COORDINATES_API_URL}/{identifier}/{reference_frame}")

        assert response.status_code == HTTPStatus.OK
        assert_json_is_equal(response.text, json.dumps(expected_response))

    @mock.patch("ska_oso_services.common.api.coordinates.get_coordinates")
    def test_not_found(self, mock_get_coordinates, client):
        """
        Test 404 when object is not found in SIMBAD or NED
        """
        mock_get_coordinates.side_effect = NotFoundError(
            "Object not found in SIMBAD or NED"
        )

        response = client.get(f"{COORDINATES_API_URL}/NOSOURCE/equatorial")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json() == {"detail": "Object not found in SIMBAD or NED"}

    def test_invalid_reference_frame(self, client):
        """
        Test 422 when reference frame is not one of 'equatorial' or 'galactic'
        """
        response = client.get(f"{COORDINATES_API_URL}/M31/unsupported-frame")

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "Input should be 'equatorial' or 'galactic'" in response.text
