# pylint: disable=E1101
# Getting several warnings of
#  '[E1101(no-member), get_systemcoordinates] Instance of 'str' has no 'ra' member'
# which makes no sense
import logging
from enum import Enum
from typing import Annotated

from fastapi import APIRouter
from pydantic import Field
from ska_oso_pdm import Target

from ska_oso_services.common.coordinateslookup import convert_icrs_to_galactic, get_coordinates
from ska_oso_services.common.model import AppModel

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/coordinates")


class ReferenceFrame(str, Enum):
    equatorial = "equatorial"
    galactic = "galactic"


class Equatorial(AppModel):
    """
    This class is deprecated as the PDM Target can be used
    instead - see GalacticResponse below.
    """

    ra: str
    dec: str
    velocity: float
    redshift: float


class Galactic(AppModel):
    """
    This class is deprecated as the PDM Target can be used
    instead - see EquatorialResponse below.
    """

    lon: float
    lat: float
    velocity: float
    redshift: float


class EquatorialResponse(Target):
    """
    Extension of the Target with the deprecated equatorial field.
    Once use of the equatorial field is removed,
    this class can be deleted and Target used.
    """

    equatorial: Annotated[
        Equatorial,
        Field(
            deprecated="Use the PDM Target object fields instead - they contain the "
            "same data that can be put straight into an SBD or Proposal"
        ),
    ]


class GalacticResponse(Target):
    """
    Extension of the Target with the deprecated galactic field.
    Once use of the galactic field is removed,
    this class can be deleted and Target used.
    """

    galactic: Annotated[
        Galactic,
        Field(
            deprecated="Use the PDM Target object fields instead - they contain the "
            "same data that can be put straight into an SBD or Proposal"
        ),
    ]


@router.get(
    "/{identifier}/{reference_frame}",
    summary="Look up the coordinates for the given object " "identifier in astronomy catalogs.",
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
    lookup_result_target = get_coordinates(identifier)

    if reference_frame == ReferenceFrame.galactic:
        galactic_coordinates = convert_icrs_to_galactic(lookup_result_target.reference_coordinate)
        lookup_result_target.reference_coordinate = galactic_coordinates
        return GalacticResponse(
            **lookup_result_target.model_dump(),
            galactic=Galactic(
                lon=galactic_coordinates.l,
                lat=galactic_coordinates.b,
                velocity=lookup_result_target.radial_velocity.quantity.value,
                redshift=lookup_result_target.radial_velocity.redshift,
            ),
        )
    else:
        return EquatorialResponse(
            **lookup_result_target.model_dump(),
            equatorial=Equatorial(
                ra=lookup_result_target.reference_coordinate.ra_str,
                dec=lookup_result_target.reference_coordinate.dec_str,
                velocity=lookup_result_target.radial_velocity.quantity.value,
                redshift=lookup_result_target.radial_velocity.redshift,
            ),
        )
