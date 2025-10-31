"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from importlib.metadata import version

from pydantic import dataclasses
from ska_ost_osd.osd.common.error_handling import OSDModelError
from ska_ost_osd.osd.models.models import OSDQueryParams
from ska_ost_osd.osd.routers.api import get_osd

from ska_oso_services.common.error_handling import OSDError
from ska_oso_services.common.model import AppModel

SUPPORTED_ARRAY_ASSEMBLIES = ["AA0.5", "AA1", "AA2"]

OSD_VERSION = version("ska-ost-osd")
OSD_SOURCE = "car"


@dataclasses.dataclass
class Band5bSubband:
    sub_band: int
    max_frequency_hz: float
    min_frequency_hz: float
    lo_frequency_hz: float
    sideband: str


@dataclasses.dataclass
class FrequencyBand:
    max_frequency_hz: float
    min_frequency_hz: float
    rx_id: str | None = None
    band5b_subbands: list[Band5bSubband] | None = None


@dataclasses.dataclass
class Subarray:
    name: str
    receptors: list[str | int]


class MidConfiguration(AppModel):
    frequency_band: list[FrequencyBand]
    subarrays: list[Subarray]


class LowConfiguration(AppModel):
    frequency_band: FrequencyBand
    subarrays: list[Subarray]


class Configuration(AppModel):
    ska_mid: MidConfiguration
    ska_low: LowConfiguration


def configuration_from_osd() -> Configuration:
    """
    Calls the OSD and converts the response into a Configuration
    with information for the UI.

    Note: currently this method uses the OSD as a library rather than
     a service. However, it calls the OSD rest functions rather than
     the lower level, as the interface is easier to use. Both of these
     things are likely to change in the future.
    """
    return Configuration(
        ska_mid=_get_mid_telescope_configuration(),
        ska_low=_get_low_telescope_configuration(),
    )


def _get_mid_telescope_configuration() -> MidConfiguration:
    subarrays = []
    for array_assembly in SUPPORTED_ARRAY_ASSEMBLIES:
        mid_response = get_osd_data(
            array_assembly=array_assembly,
            capabilities="mid",
            source=OSD_SOURCE,
            osd_version=OSD_VERSION,
        )
        subarrays.append(
            Subarray(
                name=array_assembly,
                receptors=mid_response["capabilities"]["mid"][array_assembly][
                    "number_dish_ids"
                ],
            )
        )

    # Receiver information is the same for each array assembly, as such we use the
    # last fetched response to populate this information.

    receiver_information = mid_response["capabilities"]["mid"]["basic_capabilities"][
        "receiver_information"
    ]

    def frequency_band_from_receiver_information_for_band(receiver_information):
        band5b_subbands = (
            [
                Band5bSubband(**sub_band)
                for sub_band in receiver_information["sub_bands"]
            ]
            if receiver_information["rx_id"] == "Band_5b"
            else None
        )

        return FrequencyBand(**receiver_information, band5b_subbands=band5b_subbands)

    return MidConfiguration(
        frequency_band=[
            frequency_band_from_receiver_information_for_band(receiver_info)
            for receiver_info in receiver_information
        ],
        subarrays=subarrays,
    )


def _get_low_telescope_configuration() -> LowConfiguration:
    subarrays = []
    for array_assembly in SUPPORTED_ARRAY_ASSEMBLIES:
        low_response = get_osd_data(
            array_assembly=array_assembly,
            capabilities="low",
            source=OSD_SOURCE,
            osd_version=OSD_VERSION,
        )
        subarrays.append(
            Subarray(
                name=array_assembly,
                receptors=low_response["capabilities"]["low"][array_assembly][
                    "number_station_ids"
                ],
            )
        )

    receiver_information = low_response["capabilities"]["low"]["basic_capabilities"]

    return LowConfiguration(
        frequency_band=FrequencyBand(**receiver_information), subarrays=subarrays
    )


def get_osd_data(*args, **kwargs):
    """
    Wrapper function for `get_osd` that fetches osd data

    This function constructs an `OSDQueryParams` object from the given
    arguments and keyword arguments, calls `get_osd` with these parameters,
    and returns the result data. If `get_osd` raises an `OSDModelError` or
    `ValueError`, this function wraps and raises it as an `OSDError`
    """
    try:
        params = OSDQueryParams(*args, **kwargs)
        osd_data = get_osd(params)
    except (OSDModelError, ValueError) as error:
        raise OSDError(error)
    data = (
        osd_data.model_dump()["result_data"]
        if hasattr(osd_data, "model_dump")
        else osd_data
    )
    return data
