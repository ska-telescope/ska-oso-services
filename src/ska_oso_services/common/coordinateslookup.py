# https://stackoverflow.com/a/50099819
# pylint: disable=no-member,no-name-in-module
import logging

import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.exceptions import TimeoutError  # pylint: disable=redefined-builtin
from astroquery.exceptions import RemoteServiceError, TableParseError
from astroquery.ipac.ned import Ned
from astroquery.simbad import Simbad
from ska_oso_pdm import (
    GalacticCoordinates,
    ICRSCoordinates,
    RadialVelocity,
    RadialVelocityUnits,
    Target,
)

from ska_oso_services.common.error_handling import CatalogLookupError, NotFoundError

LOGGER = logging.getLogger(__name__)


AstroqueryExceptions = (TimeoutError, TableParseError, RemoteServiceError)


def get_coordinates(object_name: str) -> Target:
    """
    Query celestial coordinates for a given object name in either the
    SIMBAD or the NED databases of astronomical sources. We search SIMBAD
    and if the source is not found, try NED.
    The function returns the Right Ascension (RA) and Declination (Dec)
    in the hour-minute-second (HMS) and degree-minute-second (DMS) format
    respectively.

    Velocities are handled in the following way:
    Simbad - for each object, a master value is stored which will be either
    a velocity or a redshift. The function finds out which one this is and
    stores it. The other is set to zero.
    NED - only the redshift is stored as the velocity has limited precision.
    Velocity is set to zero.
    """
    try:
        simbad_result = lookup_in_simbad(object_name)
        if simbad_result is not None:
            return simbad_result

    except AstroqueryExceptions:
        LOGGER.exception("Error occurred while searching SIMBAD")
        # Continue to lookup in NED

    try:
        ned_result = lookup_in_ned(object_name)
        if ned_result is not None:
            return ned_result
    except AstroqueryExceptions as err:
        LOGGER.exception("Error occurred while searching NED")
        raise CatalogLookupError(
            "Error while looking up target in SIMBAD/NED. "
            "Please try again or manually input target details."
        ) from err

    not_found_msg = f"Object {object_name} not found in SIMBAD or NED"
    LOGGER.debug(not_found_msg)
    raise NotFoundError(detail=not_found_msg)


def lookup_in_simbad(object_name: str) -> Target | None:
    LOGGER.debug("Looking up %s in SIMBAD", object_name)
    Simbad.add_votable_fields("velocity")
    result_table_simbad = Simbad.query_object(object_name)

    if len(result_table_simbad) == 0:
        return None

    ra = result_table_simbad["ra"][0]
    dec = result_table_simbad["dec"][0]
    coordinates = SkyCoord(ra, dec, unit=(u.degree, u.degree), frame="icrs")
    pdm_coordinate = _sky_coord_to_pdm_icrs(coordinates)

    # Determine if stored information is redshift or velocity
    rvz_type = result_table_simbad["rvz_type"]
    match rvz_type:
        case "z":
            radial_velocity = RadialVelocity(
                redshift=result_table_simbad["rvz_redshift"]
            )
        case "v":
            radial_velocity = RadialVelocity(
                quantity=(
                    u.Quantity(
                        value=result_table_simbad["rvz_radvel"],
                        unit=RadialVelocityUnits.KM_PER_SEC,
                    )
                )
            )
        case _:
            # The other rvz_type that might be stored in simbad are not supported
            radial_velocity = RadialVelocity()

    return Target(
        name=object_name,
        reference_coordinate=pdm_coordinate,
        radial_velocity=radial_velocity,
    )


def lookup_in_ned(object_name: str) -> Target | None:
    LOGGER.debug("Looking up %s in NED", object_name)
    result_table_ned = Ned.query_object(object_name)
    if len(result_table_ned) == 0:
        return None

    ra = result_table_ned["RA"][0]
    dec = result_table_ned["DEC"][0]
    coordinates = SkyCoord(ra, dec, unit=(u.degree, u.degree), frame="icrs")
    pdm_coordinate = _sky_coord_to_pdm_icrs(coordinates)

    # For NED we only take the redshift
    if (
        hasattr(result_table_ned["Redshift"], "mask")
        and result_table_ned["Redshift"].mask[0]
    ):
        radial_velocity = RadialVelocity(redshift=0)
    else:
        radial_velocity = RadialVelocity(redshift=result_table_ned["Redshift"][0])

    return Target(
        name=object_name,
        reference_coordinate=pdm_coordinate,
        radial_velocity=radial_velocity,
    )


def convert_icrs_to_galactic(icrs_coordinates: ICRSCoordinates) -> GalacticCoordinates:
    sky_coord = icrs_coordinates.to_sky_coord()

    return GalacticCoordinates(
        l=round(sky_coord.galactic.l.value, 2), b=round(sky_coord.galactic.b.value, 4)
    )


def _sky_coord_to_pdm_icrs(sky_coord: SkyCoord) -> ICRSCoordinates:
    return ICRSCoordinates(
        ra_str=sky_coord.icrs.ra.to_string(u.hourangle, sep=":", pad=True, precision=4),
        dec_str=sky_coord.icrs.dec.to_string(u.degree, sep=":", pad=True, precision=3),
    )
