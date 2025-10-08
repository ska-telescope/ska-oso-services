import logging
from typing import Any

from fastapi import APIRouter
from ska_aaa_authhelpers import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.sdpmapper import get_script_params, get_script_versions

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/sdp")


@router.get(
    "/scriptVersions/{name}",
    summary="Retrieving SDP script versions from TMData",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_versions(name: str) -> list[str]:
    """
    Returns a dictionary list of available SDP script versions with their
    version details for the given script.
    """
    return get_script_versions(name)


@router.get(
    "/scriptParams/{name}/{version}",
    summary="Retrieving SDP script parameters selected script",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_params(
    name: str,
    version: str,
) -> dict[str, Any]:
    """
    Returns the default parameters for the selected SDP script and version.
    """
    return get_script_params(name, version)
