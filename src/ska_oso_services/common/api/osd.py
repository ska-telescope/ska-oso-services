import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_ost_osd.osd.views.odt import Configuration

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.osdmapper import configuration_from_osd

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/osd",
    summary="Get the OSD's capabilities, constraints and defaults for both telescopes.",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_osd() -> Configuration:
    LOGGER.debug("GET /osd")
    return configuration_from_osd()
