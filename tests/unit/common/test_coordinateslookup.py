from unittest import mock

import pytest
from astropy.units import Quantity
from astroquery.exceptions import RemoteServiceError
from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target

from ska_oso_services.common.coordinateslookup import get_coordinates
from ska_oso_services.common.error_handling import CatalogLookupError, NotFoundError

DUMMY_SIMBAD_ASTROPY_TABLE = {
    "ra": [204.25383],
    "dec": [-29.865761],
    "rvz_type": "v",
    "rvz_radvel": 519.1,
}
DUMMY_NED_ASTROPY_TABLE = {"RA": [204.25383], "DEC": [-29.865761], "Redshift": [54]}

TEST_TARGET_WITH_VELOCITY = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(
        ra_str="13:37:00.9192", dec_str="-29:51:56.740"
    ),
    radial_velocity=RadialVelocity(quantity=Quantity(value=519.1, unit="km/s")),
)
TEST_TARGET_WITH_REDSHIFT = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(
        ra_str="13:37:00.9192", dec_str="-29:51:56.740"
    ),
    radial_velocity=RadialVelocity(redshift=54),
)


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
def test_found_in_simbad(mock_simbad):
    mock_simbad.query_object.return_value = DUMMY_SIMBAD_ASTROPY_TABLE
    result = get_coordinates("M83")
    assert result == TEST_TARGET_WITH_VELOCITY


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_not_found_in_simbad_found_in_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.return_value = []
    mock_ned.query_object.return_value = DUMMY_NED_ASTROPY_TABLE
    result = get_coordinates("M83")
    assert result == TEST_TARGET_WITH_REDSHIFT


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_not_found_in_simbad_or_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.return_value = []
    mock_ned.query_object.return_value = []

    with pytest.raises(NotFoundError) as err:
        get_coordinates("M83")

    assert err.value.detail == "Object M83 not found in SIMBAD or NED"


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_not_found_in_simbad_error_in_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.return_value = []
    mock_ned.query_object.side_effect = RemoteServiceError("dummy error")

    with pytest.raises(CatalogLookupError) as err:
        get_coordinates("M83")

    assert (
        err.value.detail == "Error while looking up target in SIMBAD/NED. "
        "Please try again or manually input target details."
    )


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_error_in_simbad_found_in_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.side_effect = RemoteServiceError("dummy error")
    mock_ned.query_object.return_value = DUMMY_NED_ASTROPY_TABLE
    result = get_coordinates("M83")
    assert result == TEST_TARGET_WITH_REDSHIFT


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_error_in_simbad_not_found_in_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.side_effect = RemoteServiceError("dummy error")
    mock_ned.query_object.return_value = []

    with pytest.raises(NotFoundError) as err:
        get_coordinates("M83")

    assert err.value.detail == "Object M83 not found in SIMBAD or NED"


@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_error_in_simbad_error_in_ned(mock_ned, mock_simbad):
    mock_simbad.query_object.side_effect = RemoteServiceError("dummy error")
    mock_ned.query_object.side_effect = RemoteServiceError("dummy error")
    with pytest.raises(CatalogLookupError) as err:
        get_coordinates("M83")

    assert (
        err.value.detail == "Error while looking up target in SIMBAD/NED. "
        "Please try again or manually input target details."
    )
