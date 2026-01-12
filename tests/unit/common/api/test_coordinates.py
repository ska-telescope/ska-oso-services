import json
from http import HTTPStatus
from unittest import mock

from astropy.units import Quantity
from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target

from ska_oso_services.common.error_handling import NotFoundError
from tests.unit.conftest import APP_BASE_API_URL
from tests.unit.util import assert_json_is_equal

COORDINATES_API_URL = f"{APP_BASE_API_URL}/coordinates"

TEST_TARGET_WITH_VELOCITY = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(
        ra_str="00:42:44.3300", dec_str="+41:16:07.500"
    ),
    radial_velocity=RadialVelocity(quantity=Quantity(value=519.1, unit="km/s")),
)


class TestCoordinates:

    @mock.patch("ska_oso_services.common.api.coordinates.get_coordinates")
    def test_success_equatorial(self, mock_get_coordinates, client):
        mock_get_coordinates.return_value = TEST_TARGET_WITH_VELOCITY

        expected_response = {
            "equatorial": {
                "dec": "+41:16:07.500",
                "ra": "00:42:44.3300",
                "redshift": 0.0,
                "velocity": 519.1,
            },
            "name": "M83",
            "pointing_pattern": {
                "active": "SinglePointParameters",
                "parameters": [
                    {
                        "kind": "SinglePointParameters",
                        "offset_x_arcsec": 0.0,
                        "offset_y_arcsec": 0.0,
                    }
                ],
            },
            "radial_velocity": {
                "definition": "RADIO",
                "quantity": {"unit": "km / s", "value": 519.1},
                "redshift": 0.0,
                "reference_frame": "LSRK",
            },
            "reference_coordinate": {
                "dec_str": "+41:16:07.500",
                "epoch": 2000.0,
                "kind": "icrs",
                "parallax": 0.0,
                "pm_dec": 0.0,
                "pm_ra": 0.0,
                "ra_str": "00:42:44.3300",
            },
            "target_id": "",
        }

        response = client.get(f"{COORDINATES_API_URL}/M83/equatorial")
        assert response.status_code == HTTPStatus.OK
        assert_json_is_equal(response.text, json.dumps(expected_response))

    @mock.patch("ska_oso_services.common.api.coordinates.get_coordinates")
    def test_success_galactic(self, mock_get_coordinates, client):
        mock_get_coordinates.return_value = TEST_TARGET_WITH_VELOCITY

        expected_response = {
            "galactic": {
                "lat": -21.5733088,
                "lon": 121.1743291,
                "redshift": 0.0,
                "velocity": 519.1,
            },
            "name": "M83",
            "pointing_pattern": {
                "active": "SinglePointParameters",
                "parameters": [
                    {
                        "kind": "SinglePointParameters",
                        "offset_x_arcsec": 0.0,
                        "offset_y_arcsec": 0.0,
                    }
                ],
            },
            "radial_velocity": {
                "definition": "RADIO",
                "quantity": {"unit": "km / s", "value": 519.1},
                "redshift": 0.0,
                "reference_frame": "LSRK",
            },
            "reference_coordinate": {
                "kind": "galactic",
                "l": 121.1743291,
                "b": -21.5733088,
                "epoch": 2000.0,
                "parallax": 0.0,
                "pm_l": 0.0,
                "pm_b": 0.0,
            },
            "target_id": "",
        }

        response = client.get(f"{COORDINATES_API_URL}/M83/galactic")

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
