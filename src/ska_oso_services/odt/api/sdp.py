import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.sdpmapper import get_script_params, get_script_versions

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/sdp")


@router.get(
    "/scriptVersions",
    summary="Retrieving SDP script versions from TMData",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_versions() -> list[dict]:
    """
    Returns a dictionary list of available SDP scripts with their version details.
    """
    return get_script_versions()


@router.get(
    "/scriptParams/{name}/{version}",
    summary="Retrieving SDP script parameters selected script",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_params(
    name: str,
    version: str,
) -> dict:
    """
    Returns the default parameters for the selected SDP script and version.
    """
    return get_script_params(name, version)
