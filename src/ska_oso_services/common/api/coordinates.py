# pylint: disable=E1101
# Getting several warnings of
#  '[E1101(no-member), get_systemcoordinates] Instance of 'str' has no 'ra' member'
# which makes no sense
import logging
from enum import Enum

from fastapi import APIRouter

from ska_oso_services.common.coordinateslookup import (
    Equatorial,
    Galactic,
    convert_to_galactic,
    get_coordinates,
    round_coord,
)
from ska_oso_services.common.model import AppModel

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/coordinates")


class ReferenceFrame(str, Enum):
    equatorial = "equatorial"
    galactic = "galactic"


class EquatorialResponse(AppModel):
    equatorial: Equatorial


class GalacticResponse(AppModel):
    galactic: Galactic


@router.get(
    "/{identifier}/{reference_frame}",
    summary="Look up the coordinates for the given object "
    "identifier in astronomy catalogs.",
)
def get_systemcoordinates(
    identifier: str, reference_frame: ReferenceFrame
) -> GalacticResponse | EquatorialResponse:
    """
    Function that requests to /coordinates/{identifier}/{reference_frame} is mapped to

    Query celestial coordinates for a given object name from SIMBAD and NED databases.
    If the object is not found in SIMBAD database
    it then queries the NED (NASA/IPAC Extragalactic Database).

    :param identifier: A string representing the name of the object to query.
    :param reference_frame: A string representing the reference frame
    to return the coordinates in ("galactic" or "equatorial").
    :return: A response with one key "equatorial" or "galactic",
             containing a nested dictionary with galactic or equatorial coordinates:
             {"galactic":
                {"latitude": 78.7068,"longitude": 42.217}
             } or {"equatorial":
                {"right_ascension": "+28:22:38.200",
                "declination": "13:41:11.620"}
             }
             In case of an error, an error response is returned.
    :rtype: GalacticResponse | EquatorialResponse
    """
    LOGGER.debug("GET coordinates: %s", identifier)
    response = get_coordinates(identifier)

    if reference_frame.lower() == "galactic":
        return GalacticResponse(
            galactic=convert_to_galactic(
                response.ra, response.dec, response.velocity, response.redshift
            )
        )
    else:
        return EquatorialResponse(
            equatorial=round_coord(
                response.ra, response.dec, response.velocity, response.redshift
            )
        )
