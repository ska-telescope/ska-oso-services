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


class Station(AppModel):
    id: int
    label: str


class SubarrayDetail(AppModel):
    name: str
    allowed_stations: list[Station]


class _ItfSubarrayCache:
    """
    Holds the loaded subarrays. A complete load is kept until a refresh is
    requested. After a failed or incomplete load the usable subarrays are kept,
    and the source is tried again on a later call. The source is fetched at most
    once per retry interval.
    """

    def __init__(self):
        self.subarrays: list[SubarrayDetail] | None = None
        self.complete: bool = False
        self.retry_after: float = 0.0

    def clear(self):
        self.subarrays = None
        self.complete = False
        self.retry_after = 0.0


_CACHE = _ItfSubarrayCache()


def get_itf_subarrays(refresh: bool = False) -> list[SubarrayDetail]:
    """
    Fetches the SKA Low ITF subarrays and their allowed stations from the TMData.

    Each top level directory in the TMData that contains an array.yaml and
    stations.yaml is treated as an ITF environment, so new environments are
    picked up without a code change.

    :param refresh: Fetch the data again even if a complete load is cached. This
        is still limited to one fetch per retry interval, so the cached subarrays
        are returned if the source was fetched recently.
    :return: A subarray for each ITF environment that could be parsed, or an
        empty list if the LOW_ITF_TMDATA source is not set or the data has not
        been retrieved.
    """
    if _CACHE.complete and not refresh:
        return _CACHE.subarrays

    tmdata_path = get_settings().low_itf_tmdata
    if not tmdata_path:
        return []
    if time.monotonic() < _CACHE.retry_after:
        return _CACHE.subarrays or []

    _CACHE.retry_after = time.monotonic() + RETRY_INTERVAL_SECONDS
    try:
        tmdata = TMData([tmdata_path], update=True)
        subarrays, complete = _get_itf_subarrays(tmdata)
    except Exception:  # the TMData backends raise a wide range of errors
        LOGGER.warning(
            "Unable to retrieve SKA Low ITF subarrays from TMData source %s. "
            "Any previously retrieved subarrays will be used.",
            tmdata_path,
            exc_info=True,
        )
        return _CACHE.subarrays or []

    _CACHE.subarrays = subarrays
    _CACHE.complete = complete
    return subarrays


def _get_itf_subarrays(tmdata: TMData) -> tuple[list[SubarrayDetail], bool]:
    """
    :return: The subarrays for the environments that could be parsed, and
        whether every environment was parsed.
    """
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
    return subarrays, len(subarrays) == len(environments)


def _get_itf_subarray(tmdata: TMData, environment: str) -> SubarrayDetail:
    array = tmdata[f"{environment}/{ARRAY_FILE}"].get_dict()["platform"]["array"]
    stations = tmdata[f"{environment}/{STATIONS_FILE}"].get_dict()["platform"]["stations"]

    return SubarrayDetail(
        name=array["name"],
        allowed_stations=[
            Station(id=stations[label]["id"], label=label) for label in array["stations"]
        ],
    )
