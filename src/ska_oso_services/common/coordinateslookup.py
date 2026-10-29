from __future__ import annotations

# https://stackoverflow.com/a/50099819
# pylint: disable=no-member,no-name-in-module
import logging
from collections.abc import Callable, Sequence
from enum import StrEnum
from functools import cache
from typing import NamedTuple

import astropy.units as u
import requests
from astropy.coordinates import SkyCoord
from astroquery.exceptions import RemoteServiceError, TableParseError
from astroquery.ipac.ned import Ned
from astroquery.simbad import SimbadClass
from pyvo.dal.exceptions import DALAccessError
from requests.adapters import HTTPAdapter
from ska_oso_pdm import (
    GalacticCoordinates,
    ICRSCoordinates,
    RadialVelocity,
    RadialVelocityUnits,
    Target,
)

from ska_oso_services.common.error_handling import CatalogLookupError, NotFoundError

LOGGER = logging.getLogger(__name__)

# Seconds to wait for any single catalogue request. Without this an unresponsive
# server (e.g. during a CDS outage) can block a lookup for several minutes.
CATALOGUE_TIMEOUT_S = 10

# SIMBAD is hosted by CDS, with a mirror at Harvard that is tried if CDS is unavailable
SIMBAD_SERVERS = ("simbad.cds.unistra.fr", "simbad.harvard.edu")

# NED reports an unknown object as an error rather than as an empty result
NED_NOT_FOUND_MESSAGE = "not currently recognized by the NED name interpreter"

Ned.TIMEOUT = CATALOGUE_TIMEOUT_S


class ReferenceFrame(StrEnum):
    equatorial = "equatorial"
    galactic = "galactic"


class Catalogue(StrEnum):
    simbad = "simbad"
    ned = "ned"


# The catalogues to query, in order, when the caller doesn't specify them
DEFAULT_CATALOGUES = (Catalogue.simbad, Catalogue.ned)


class CatalogueResult(NamedTuple):
    coordinate: SkyCoord
    radial_velocity: RadialVelocity


class CatalogueUnavailableError(Exception):
    """Raised when a catalogue cannot be queried, e.g. it is down or timed out."""


CatalogueLookup = Callable[[str], CatalogueResult | None]


def _as_python_scalar(value):
    """Convert table/array-like values to plain Python scalars where possible."""
    if isinstance(value, (str, int, float)):
        return value

    # Numpy / masked scalar
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError, TypeError:
            pass

    # 1-element containers/columns
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        try:
            if len(value) == 1:
                first = value[0]
                return first.item() if hasattr(first, "item") else first
        except TypeError, IndexError, KeyError:
            pass

    return value


def get_coordinates(
    object_name: str,
    reference_frame: ReferenceFrame,
    catalogues: Sequence[Catalogue] = DEFAULT_CATALOGUES,
) -> Target:
    """
    Query celestial coordinates for a given object name. Each catalogue is
    queried in turn (by default SIMBAD then NED) and the first match is returned.
    A catalogue that is unavailable is skipped.

    Velocities are handled in the following way:
    Simbad - for each object, a master value is stored which will be either
    a velocity, a redshift or a cz. The function finds out which one this is and
    stores it, with a cz stored as its redshift. The other is set to zero.
    NED - only the redshift is stored as the velocity has limited precision.
    Velocity is set to zero.

    :param object_name: The name of the object to be queried
    :param reference_frame: Reference frame of the object coordinates to be
        returned
    :param catalogues: The catalogues to query, in order of preference
    :raises NotFoundError: if the object is not in any of the catalogues
    :raises CatalogLookupError: if the object was not found and at least one
        of the catalogues could not be queried
    """
    unavailable = []
    for catalogue in catalogues:
        try:
            result = get_catalogue_lookup(catalogue)(object_name)
        except CatalogueUnavailableError as err:
            LOGGER.warning("Skipping %s as it is unavailable: %s", catalogue.upper(), err)
            unavailable.append(catalogue)
            continue

        if result is not None:
            if reference_frame == ReferenceFrame.galactic:
                reference_coordinate = _sky_coord_to_pdm_gal(result.coordinate)
            else:
                reference_coordinate = _sky_coord_to_pdm_icrs(result.coordinate)

            return Target(
                name=object_name,
                reference_coordinate=reference_coordinate,
                radial_velocity=result.radial_velocity,
            )

    if unavailable:
        raise CatalogLookupError(
            f"Unable to look up {object_name} as {_join_names(unavailable)} could not be "
            "reached. Please try again later or manually input target details."
        )

    raise NotFoundError(
        f"Object {object_name} not found in {_join_names(catalogues)}. "
        "Please try again or manually input target details."
    )


def get_catalogue_lookup(catalogue: Catalogue) -> CatalogueLookup:
    """
    Return the function that looks up an object in the given catalogue.

    Each lookup function returns a CatalogueResult if the object is found, None if
    it is not, and raises CatalogueUnavailableError if the catalogue can't be queried.
    """
    match catalogue:
        case Catalogue.simbad:
            return lookup_in_simbad
        case Catalogue.ned:
            return lookup_in_ned
    raise ValueError(f"No lookup available for catalogue {catalogue}")


def lookup_in_simbad(object_name: str) -> CatalogueResult | None:
    for server in SIMBAD_SERVERS:
        LOGGER.debug("Looking up %s in SIMBAD at %s", object_name, server)
        try:
            result_table_simbad = _simbad_client(server).query_object(object_name)
            break
        except (DALAccessError, requests.RequestException) as err:
            LOGGER.warning("SIMBAD server %s could not be queried: %s", server, err)
    else:
        raise CatalogueUnavailableError(f"No SIMBAD server could be reached: {SIMBAD_SERVERS}")

    if len(result_table_simbad) == 0:
        return None

    coordinate = SkyCoord(
        result_table_simbad["ra"][0],
        result_table_simbad["dec"][0],
        unit=(u.degree, u.degree),
        frame="icrs",
    )

    # Determine if stored information is redshift or velocity. A cz value ("c") is
    # also stored as its redshift, whereas its rvz_radvel is a derived relativistic velocity
    rvz_type = _as_python_scalar(result_table_simbad["rvz_type"])
    match rvz_type:
        case "z" | "c":
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

    return CatalogueResult(coordinate=coordinate, radial_velocity=radial_velocity)


def lookup_in_ned(object_name: str) -> CatalogueResult | None:
    LOGGER.debug("Looking up %s in NED", object_name)
    try:
        result_table_ned = Ned.query_object(object_name)
    except RemoteServiceError as err:
        if NED_NOT_FOUND_MESSAGE in str(err):
            return None
        raise CatalogueUnavailableError(f"NED returned an error: {err}") from err
    except (TableParseError, requests.RequestException) as err:
        raise CatalogueUnavailableError(f"NED could not be queried: {err}") from err

    if len(result_table_ned) == 0:
        return None

    coordinate = SkyCoord(
        result_table_ned["RA"][0],
        result_table_ned["DEC"][0],
        unit=(u.degree, u.degree),
        frame="icrs",
    )

    # For NED we only take the redshift
    if hasattr(result_table_ned["Redshift"], "mask") and result_table_ned["Redshift"].mask[0]:
        radial_velocity = RadialVelocity(redshift=0)
    else:
        radial_velocity = RadialVelocity(
            redshift=float(_as_python_scalar(result_table_ned["Redshift"][0]))
        )

    return CatalogueResult(coordinate=coordinate, radial_velocity=radial_velocity)


class _TimeoutHTTPAdapter(HTTPAdapter):
    """Applies CATALOGUE_TIMEOUT_S to any request sent without its own timeout."""

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = CATALOGUE_TIMEOUT_S
        return super().send(request, **kwargs)


@cache
def _simbad_client(server: str) -> SimbadClass:
    """
    Return a SIMBAD client for the given server that also returns velocities.
    Clients are reused so the requests made while setting one up only happen once
    per server, leaving a single request per lookup.
    """
    simbad = SimbadClass()
    simbad.server = server
    # astroquery doesn't set an HTTP timeout on SIMBAD's TAP requests, and setting
    # SimbadClass.timeout makes a request to the server, so add one to its session.
    simbad._session.mount("https://", _TimeoutHTTPAdapter())
    simbad.add_votable_fields("velocity")
    return simbad


def _join_names(catalogues: Sequence[Catalogue]) -> str:
    return " or ".join(catalogue.upper() for catalogue in catalogues)


def _sky_coord_to_pdm_icrs(sky_coord: SkyCoord) -> ICRSCoordinates:
    return ICRSCoordinates(
        ra_str=sky_coord.icrs.ra.to_string(u.hourangle, sep=":", pad=True, precision=4),
        dec_str=sky_coord.icrs.dec.to_string(u.degree, sep=":", pad=True, precision=3),
    )


def _sky_coord_to_pdm_gal(sky_coord: SkyCoord) -> GalacticCoordinates:
    return GalacticCoordinates(
        l=round(float(sky_coord.galactic.l.deg), 7), b=round(float(sky_coord.galactic.b.deg), 7)
    )
