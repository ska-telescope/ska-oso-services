import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.itfmapper import get_itf_subarrays
from ska_oso_services.common.osdmapper import Configuration, configuration_from_osd

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/configuration",
    summary="Get static configuration data used by the ODT UI that is sourced from the OSD "
    "and the SKA Low ITF telescope model data.",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def configuration_get() -> Configuration:
    LOGGER.debug("GET /configuration")
    configuration = configuration_from_osd()
    # The ITF subarrays are added here as this data is quite both in content and intention
    # from the OSD definition of a subarray.
    return configuration.model_copy(
        update={
            "ska_low": configuration.ska_low.model_copy(
                update={"itf_subarrays": get_itf_subarrays()}
            )
        }
    )
