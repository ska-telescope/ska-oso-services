import logging

from fastapi import APIRouter

from ska_oso_services.common.osdmapper import Configuration, configuration_from_osd

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/configuration",
    summary="Get static configuration data used by the ODT UI "
    "that is sourced from the OSD.",
)
def configuration_get() -> Configuration:
    LOGGER.debug("GET /configuration")
    return configuration_from_osd()
