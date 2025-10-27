import json
from http import HTTPStatus
from unittest import mock

from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target

from tests.unit.conftest import APP_BASE_API_URL
from tests.unit.util import assert_json_is_equal

CALIBRATOR_API_URL = f"{APP_BASE_API_URL}/calibrators"

mocked_return = [
    Target(
        target_id="calibrator-00001",
        name="3C 444",
        reference_coordinate=ICRSCoordinates(
            ra_str="22:14:25.752", dec_str="-17:01:36.29"
        ),
        radial_velocity=RadialVelocity(redshift=0.153053),
    ),
    Target(
        target_id="calibrator-00002",
        name="Centaurus A",
        reference_coordinate=ICRSCoordinates(
            ra_str="13:25:27.6152", dec_str="-43:01:08.805"
        ),
        radial_velocity=RadialVelocity(redshift=0.00187695),
    ),
]

api_response = [
    {
        "target_id": "calibrator-00001",
        "name": "3C 444",
        "pointing_pattern": {
            "active": "SinglePointParameters",
            "parameters": [
                {
                    "kind": "SinglePointParameters",
                    "offset_x_arcsec": 0,
                    "offset_y_arcsec": 0,
                }
            ],
        },
        "reference_coordinate": {
            "kind": "icrs",
            "ra_str": "22:14:25.752",
            "dec_str": "-17:01:36.29",
            "pm_ra": 0,
            "pm_dec": 0,
            "parallax": 0,
            "epoch": 2000,
        },
        "radial_velocity": {
            "quantity": {"value": 0, "unit": "km / s"},
            "definition": "RADIO",
            "reference_frame": "LSRK",
            "redshift": 0.153053,
        },
    },
    {
        "target_id": "calibrator-00002",
        "name": "Centaurus A",
        "pointing_pattern": {
            "active": "SinglePointParameters",
            "parameters": [
                {
                    "kind": "SinglePointParameters",
                    "offset_x_arcsec": 0,
                    "offset_y_arcsec": 0,
                }
            ],
        },
        "reference_coordinate": {
            "kind": "icrs",
            "ra_str": "13:25:27.6152",
            "dec_str": "-43:01:08.805",
            "pm_ra": 0,
            "pm_dec": 0,
            "parallax": 0,
            "epoch": 2000,
        },
        "radial_velocity": {
            "quantity": {"value": 0, "unit": "km / s"},
            "definition": "RADIO",
            "reference_frame": "LSRK",
            "redshift": 0.00187695,
        },
    },
]


class TestCalibrators:
    @mock.patch("ska_oso_services.common.api.calibrators.to_pdm_targets")
    def test_success(
        self,
        mock_to_pdm_target,
        client,
    ):
        """
        Test successful calibrator query
        """
        mock_to_pdm_target.return_value = mocked_return

        response = client.get(f"{CALIBRATOR_API_URL}")

        assert response.status_code == HTTPStatus.OK
        assert_json_is_equal(response.text, json.dumps(api_response))
