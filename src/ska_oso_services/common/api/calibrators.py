import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_oso_pdm import Target

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.calibrators import calibrator_table, to_pdm_target

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/calibrators",
    summary="Look up a list of suitable calibrators",
    response_model=list[Target],
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_calibrators() -> list[Target]:
    """
    function to return a list of PDM Target objects derived from an AstroPy QTable
    of suitable calibrators
    """
    suitable_calibrators = to_pdm_target(calibrator_table)

    return suitable_calibrators
