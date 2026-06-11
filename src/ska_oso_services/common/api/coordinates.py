# pylint: disable=E1101
# Getting several warnings of
#  '[E1101(no-member), get_systemcoordinates] Instance of 'str' has no 'ra' member'
# which makes no sense
import logging

from fastapi import APIRouter
from ska_oso_pdm import Target

from ska_oso_services.common.coordinateslookup import ReferenceFrame, get_coordinates

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/coordinates")


@router.get(
    "/{identifier}/{reference_frame}",
    summary="Look up the coordinates for the given object " "identifier in astronomy catalogs.",
)
def get_systemcoordinates(identifier: str, reference_frame: ReferenceFrame) -> Target:
    """
    Function that requests to /coordinates/{identifier}/{reference_frame} is mapped to

    Query celestial coordinates for a given object name from SIMBAD, NED and Vizier databases.

    :param identifier: A string representing the name of the object to query.
    :param reference_frame: A string representing the reference frame
    to return the coordinates in ("galactic" or "equatorial").
    :return: An OSO PDM Target object with the name, reference_coordinates and radial
    velocity populated.
    :rtype: Target
    """
    LOGGER.debug("GET coordinates: %s", identifier)
    lookup_result_target = get_coordinates(identifier, reference_frame)

    return lookup_result_target
