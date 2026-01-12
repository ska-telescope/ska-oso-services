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
                "name": "47 Tuc",
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
                "reference_coordinate": {
                    "kind": "icrs",
                    "ra_str": "00:24:05.3590",
                    "dec_str": "-72:04:53.200",
                    "pm_ra": 0.0,
                    "pm_dec": 0.0,
                    "parallax": 0.0,
                    "epoch": 2000.0,
                },
                "radial_velocity": {
                    "quantity": {"value": -17.2, "unit": "km / s"},
                    "definition": "RADIO",
                    "reference_frame": "LSRK",
                    "redshift": 0.0,
                },
                "equatorial": {
                    "ra": "00:24:05.3590",
                    "dec": "-72:04:53.200",
                    "velocity": -17.2,
                    "redshift": 0.0,
                },
            },
        ),
        (
            "47 Tuc",
            "galactic",
            {
                "name": "47 Tuc",
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
                "reference_coordinate": {
                    "kind": "galactic",
                    "l": 305.8953327,
                    "b": -44.8891135,
                    "pm_l": 0.0,
                    "pm_b": 0.0,
                    "epoch": 2000.0,
                    "parallax": 0.0,
                },
                "radial_velocity": {
                    "quantity": {"value": -17.2, "unit": "km / s"},
                    "definition": "RADIO",
                    "reference_frame": "LSRK",
                    "redshift": 0.0,
                },
                "galactic": {
                    "lon": 305.8953327,
                    "lat": -44.8891135,
                    "velocity": -17.2,
                    "redshift": 0.0,
                },
            },
        ),
        (
            "M31",
            "equatorial",
            {
                "name": "M31",
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
                "reference_coordinate": {
                    "kind": "icrs",
                    "ra_str": "00:42:44.3300",
                    "dec_str": "41:16:07.500",
                    "pm_ra": 0.0,
                    "pm_dec": 0.0,
                    "parallax": 0.0,
                    "epoch": 2000.0,
                },
                "radial_velocity": {
                    "quantity": {
                        "value": -300.0,
                        "unit": "km / s",
                    },
                    "definition": "RADIO",
                    "reference_frame": "LSRK",
                    "redshift": 0.0,
                },
                "equatorial": {
                    "ra": "00:42:44.3300",
                    "dec": "41:16:07.500",
                    "velocity": -300.0,
                    "redshift": 0.0,
                },
            },
        ),
        (
            "N10",
            "galactic",
            {
                "name": "N10",
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
                "reference_coordinate": {
                    "kind": "galactic",
                    "l": 354.2101595,
                    "b": -78.5856477,
                    "pm_l": 0.0,
                    "pm_b": 0.0,
                    "epoch": 2000.0,
                    "parallax": 0.0,
                },
                "radial_velocity": {
                    "quantity": {"value": 6800.0, "unit": "km / s"},
                    "definition": "RADIO",
                    "reference_frame": "LSRK",
                    "redshift": 0.0,
                },
                "galactic": {
                    "lat": -78.5856477,
                    "lon": 354.2101595,
                    "redshift": 0.0,
                    "velocity": 6800.0,
                },
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
    assert (
        response.json()["reference_coordinate"]
        == expected_response["reference_coordinate"]
    )
