from unittest import mock

import pytest
from astropy.coordinates import SkyCoord
from astropy.coordinates.name_resolve import NameResolveError
from astropy.units import Quantity
from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target

from ska_oso_services.common.coordinateslookup import ReferenceFrame, get_coordinates
from ska_oso_services.common.error_handling import CatalogLookupError, NotFoundError

DUMMY_GET_ICRS_COORDINATES_RESP = SkyCoord(
    ra=Quantity(204.25383, unit="degree"), dec=Quantity(-29.86576111, unit="degree")
)


DUMMY_SIMBAD_ASTROPY_TABLE = {
    "ra": [204.25383],
    "dec": [-29.865761],
    "rvz_type": "v",
    "rvz_radvel": 519.1,
}
DUMMY_NED_ASTROPY_TABLE = {"RA": [204.25383], "DEC": [-29.865761], "Redshift": [54]}

TEST_TARGET_WITH_VELOCITY = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(ra_str="13:37:00.9192", dec_str="-29:51:56.740"),
    radial_velocity=RadialVelocity(quantity=Quantity(value=519.1, unit="km/s")),
)
TEST_TARGET_WITH_REDSHIFT = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(ra_str="13:37:00.9192", dec_str="-29:51:56.740"),
    radial_velocity=RadialVelocity(redshift=54),
)

TEST_TARGET_WITHOUT_REDSHIFT = Target(
    name="M83",
    reference_coordinate=ICRSCoordinates(ra_str="13:37:00.9192", dec_str="-29:51:56.740"),
    radial_velocity=RadialVelocity(quantity=Quantity(value=0, unit="km/s")),
)


@mock.patch("ska_oso_services.common.coordinateslookup.get_icrs_coordinates")
@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
def test_found_in_sesame_and_simbad(mock_simbad, mock_get_icrs_coordinates):
    mock_get_icrs_coordinates.return_value = DUMMY_GET_ICRS_COORDINATES_RESP
    mock_simbad.query_object.return_value = DUMMY_SIMBAD_ASTROPY_TABLE
    result = get_coordinates("M83", ReferenceFrame.equatorial)
    assert result == TEST_TARGET_WITH_VELOCITY


@mock.patch("ska_oso_services.common.coordinateslookup.get_icrs_coordinates")
@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_found_in_sesame_not_found_in_simbad_found_in_ned(
    mock_ned, mock_simbad, mock_get_icrs_coordinates
):
    mock_get_icrs_coordinates.return_value = DUMMY_GET_ICRS_COORDINATES_RESP
    mock_simbad.query_object.return_value = []
    mock_ned.query_object.return_value = DUMMY_NED_ASTROPY_TABLE
    result = get_coordinates("M83", ReferenceFrame.equatorial)
    assert result == TEST_TARGET_WITH_REDSHIFT


@mock.patch("ska_oso_services.common.coordinateslookup.get_icrs_coordinates")
@mock.patch("ska_oso_services.common.coordinateslookup.Simbad")
@mock.patch("ska_oso_services.common.coordinateslookup.Ned")
def test_found_in_sesame_not_found_in_simbad_or_ned(
    mock_ned, mock_simbad, mock_get_icrs_coordinates
):
    mock_get_icrs_coordinates.return_value = DUMMY_GET_ICRS_COORDINATES_RESP
    mock_simbad.query_object.return_value = []
    mock_ned.query_object.return_value = []
    result = get_coordinates("M83", ReferenceFrame.equatorial)
    assert result == TEST_TARGET_WITHOUT_REDSHIFT


@mock.patch("ska_oso_services.common.coordinateslookup.get_icrs_coordinates")
def test_not_found_in_sesame(mock_get_icrs_coordinates):
    mock_get_icrs_coordinates.side_effect = NameResolveError(
        "Unable to find coordinates for name '{name}' in database"
    )
    with pytest.raises(NotFoundError) as err:
        get_coordinates("dummy name", ReferenceFrame.equatorial)

    assert (
        err.value.detail == "Object dummy name not found in SIMBAD, NED or VizieR. "
        "Please try again or manually input target details."
    )


@mock.patch("ska_oso_services.common.coordinateslookup.get_icrs_coordinates")
def test_not_found_in_sesame_catalogue_error(mock_get_icrs_coordinates):
    mock_get_icrs_coordinates.side_effect = NameResolveError("All Sesame queries failed.")
    with pytest.raises(CatalogLookupError):
        get_coordinates("dummy name", ReferenceFrame.equatorial)
