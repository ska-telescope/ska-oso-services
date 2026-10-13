"""
This module retrieves the SKA Low ITF array definitions from TMData and converts
them into the subarray information needed by the application. It uses the
ska_telmodel_client library to access TMData.

The ITF data is supplementary to the configuration sourced from the OSD, so a
missing or unreachable source results in an empty list rather than an error.
"""

import logging
import time

from ska_telmodel_client import TMData

from ska_oso_services.common.model import AppModel
from ska_oso_services.settings import get_settings

LOGGER = logging.getLogger(__name__)

# Each ITF environment (e.g. em, ci) has its own top level directory in the TMData
# which contains these files
ARRAY_FILE = "array.yaml"
STATIONS_FILE = "stations.yaml"

# How long to wait after a failed lookup before trying the TMData source again,
# so that an unreachable source does not slow down every request.
RETRY_INTERVAL_SECONDS = 300


class ItfStation(AppModel):
    id: int
    label: str


class ItfSubarray(AppModel):
    name: str
    allowed_stations: list[ItfStation]


class _ItfSubarrayCache:
    """
    Holds the successfully loaded subarrays for the lifetime of the process.
    Failures are not cached, other than to delay the next attempt.
    """

    def __init__(self):
        self.subarrays: list[ItfSubarray] | None = None
        self.retry_after: float = 0.0

    def clear(self):
        self.subarrays = None
        self.retry_after = 0.0


_CACHE = _ItfSubarrayCache()


def get_itf_subarrays() -> list[ItfSubarray]:
    """
    Fetches the SKA Low ITF subarrays and their allowed stations from the TMData.

    Each top level directory in the TMData that contains an array.yaml and
    stations.yaml is treated as an ITF environment, so new environments are
    picked up without a code change.

    :return: A subarray for each ITF environment, or an empty list if the
        LOW_ITF_TMDATA source is not set or the data cannot be retrieved.
    """
    if _CACHE.subarrays is not None:
        return _CACHE.subarrays

    tmdata_path = get_settings().low_itf_tmdata
    if not tmdata_path or time.monotonic() < _CACHE.retry_after:
        return []

    try:
        tmdata = TMData([tmdata_path], update=True)
        subarrays = _get_itf_subarrays(tmdata)
    except Exception:  # the TMData backends raise a wide range of errors
        LOGGER.warning(
            "Unable to retrieve SKA Low ITF subarrays from TMData source %s. "
            "They will be omitted from the configuration.",
            tmdata_path,
            exc_info=True,
        )
        _CACHE.retry_after = time.monotonic() + RETRY_INTERVAL_SECONDS
        return []

    _CACHE.subarrays = subarrays
    return subarrays


def _get_itf_subarrays(tmdata: TMData) -> list[ItfSubarray]:
    keys = set(tmdata)
    environments = sorted(
        key.split("/")[0]
        for key in keys
        if key.count("/") == 1
        and key.endswith(f"/{ARRAY_FILE}")
        and f"{key.split('/')[0]}/{STATIONS_FILE}" in keys
    )

    subarrays = []
    for environment in environments:
        try:
            subarrays.append(_get_itf_subarray(tmdata, environment))
        except Exception:  # one malformed environment should not hide the others
            LOGGER.warning(
                "Unable to parse the SKA Low ITF '%s' environment from TMData. "
                "It will be omitted from the configuration.",
                environment,
                exc_info=True,
            )
    return subarrays


def _get_itf_subarray(tmdata: TMData, environment: str) -> ItfSubarray:
    array = tmdata[f"{environment}/{ARRAY_FILE}"].get_dict()["platform"]["array"]
    stations = tmdata[f"{environment}/{STATIONS_FILE}"].get_dict()["platform"]["stations"]

    return ItfSubarray(
        name=array["name"],
        allowed_stations=[
            ItfStation(id=stations[label]["id"], label=label) for label in array["stations"]
        ],
    )
