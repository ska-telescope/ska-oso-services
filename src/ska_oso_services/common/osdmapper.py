"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from typing import Optional

from pydantic import dataclasses
from ska_ost_osd.rest.api.resources import get_osd

from ska_oso_services.common.model import AppModel

SUPPORTED_ARRAY_ASSEMBLIES = ["AA0.5", "AA1"]


@dataclasses.dataclass
class FrequencyBand:
    max_frequency_hz: float
    min_frequency_hz: float
    rx_id: Optional[str] = None


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
        mid_response = get_osd(
            array_assembly=array_assembly, capabilities="mid", source="car"
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
    return MidConfiguration(
        frequency_band=[
            FrequencyBand(**reciever_info) for reciever_info in receiver_information
        ],
        subarrays=subarrays,
    )


def _get_low_telescope_configuration() -> LowConfiguration:
    subarrays = []
    for array_assembly in SUPPORTED_ARRAY_ASSEMBLIES:
        low_response = get_osd(
            array_assembly=array_assembly, capabilities="low", source="car"
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
