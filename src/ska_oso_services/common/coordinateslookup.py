from __future__ import annotations

# https://stackoverflow.com/a/50099819
# pylint: disable=no-member,no-name-in-module
import logging
from enum import Enum

import astropy.units as u
from astropy.coordinates import SkyCoord, get_icrs_coordinates
from astropy.coordinates.name_resolve import NameResolveError
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


class ReferenceFrame(str, Enum):
    equatorial = "equatorial"
    galactic = "galactic"


def _as_python_scalar(value):
    """Convert table/array-like values to plain Python scalars where possible."""
    if isinstance(value, (str, int, float)):
        return value

    # Numpy / masked scalar
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    # 1-element containers/columns
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        try:
            if len(value) == 1:
                first = value[0]
                return first.item() if hasattr(first, "item") else first
        except (TypeError, IndexError, KeyError):
            pass

    return value


def get_coordinates(object_name: str, reference_frame: ReferenceFrame) -> Target:
    """
    Query celestial coordinates for a given object name using sesame.
    This queries the  SIMBAD, NED and Vizier databases of astronomical
    sources.

    Velocities are handled in the following way:
    Simbad - for each object, a master value is stored which will be either
    a velocity or a redshift. The function finds out which one this is and
    stores it. The other is set to zero.
    NED - only the redshift is stored as the velocity has limited precision.
    Velocity is set to zero.

    :param object_name: The name of the object to be queried
    :param reference_frame: Reference frame of the object coordinates to be
        returned
    """
    try:
        sesame_result = get_icrs_coordinates(object_name)

        if reference_frame == ReferenceFrame.equatorial:
            reference_coordinate = _sky_coord_to_pdm_icrs(sesame_result)
        else:
            reference_coordinate = _sky_coord_to_pdm_gal(sesame_result)

        return Target(
            name=object_name,
            reference_coordinate=reference_coordinate,
            radial_velocity=get_radial_motion(object_name),
        )

    except NameResolveError as err:
        LOGGER.exception("Error occurred executing Sesame query")
        msg = str(err)

        if msg.startswith("Unable to find coordinates for name"):
            raise NotFoundError(
                f"Object {object_name} not found in SIMBAD, NED or VizieR. "
                "Please try again or manually input target details."
            )
        else:
            raise CatalogLookupError(
                "Error occurred while resolving target. "
                "Please try again or manually input target details."
            )


def get_radial_motion(object_name: str) -> RadialVelocity | None:
    LOGGER.debug("Looking up radial velocity for %s in SIMBAD", object_name)
    Simbad.add_votable_fields("velocity")
    result_table_simbad = Simbad.query_object(object_name)

    if len(result_table_simbad) != 0:
        # Determine if stored information is redshift or velocity
        rvz_type = _as_python_scalar(result_table_simbad["rvz_type"])
        match rvz_type:
            case "z":
                radial_velocity = RadialVelocity(
                    redshift=float(_as_python_scalar(result_table_simbad["rvz_redshift"]))
                )
            case "v":
                radial_velocity = RadialVelocity(
                    quantity=(
                        u.Quantity(
                            value=float(_as_python_scalar(result_table_simbad["rvz_radvel"])),
                            unit=RadialVelocityUnits.KM_PER_SEC,
                        )
                    )
                )
            case _:
                # The other rvz_type that might be stored in simbad are not supported
                radial_velocity = RadialVelocity()

    else:
        LOGGER.debug("Looking up %s in NED", object_name)
        result_table_ned = Ned.query_object(object_name)
        if len(result_table_ned) == 0:
            radial_velocity = RadialVelocity()

        # For NED we only take the redshift
        elif (
            hasattr(result_table_ned["Redshift"], "mask") and result_table_ned["Redshift"].mask[0]
        ):
            radial_velocity = RadialVelocity(redshift=0)
        else:
            radial_velocity = RadialVelocity(
                redshift=float(_as_python_scalar(result_table_ned["Redshift"][0]))
            )

    return radial_velocity


def _sky_coord_to_pdm_icrs(sky_coord: SkyCoord) -> ICRSCoordinates:
    return ICRSCoordinates(
        ra_str=sky_coord.icrs.ra.to_string(u.hourangle, sep=":", pad=True, precision=4),
        dec_str=sky_coord.icrs.dec.to_string(u.degree, sep=":", pad=True, precision=3),
    )


def _sky_coord_to_pdm_gal(sky_coord: SkyCoord) -> GalacticCoordinates:
    return GalacticCoordinates(
        l=round(float(sky_coord.galactic.l.deg), 7), b=round(float(sky_coord.galactic.b.deg), 7)
    )
