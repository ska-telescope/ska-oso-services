"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from typing import Optional

from pydantic import dataclasses
from ska_ost_osd.rest.api.resources import get_osd

from ska_oso_services.common.model import AppModel


@dataclasses.dataclass
class FrequencyBand:
    max_frequency_hz: float
    min_frequency_hz: float
    rx_id: Optional[str] = None


class MidConfiguration(AppModel):
    frequency_band: list[FrequencyBand]


class LowConfiguration(AppModel):
    frequency_band: FrequencyBand


class Configuration(AppModel):
    ska_mid: MidConfiguration
    ska_low: LowConfiguration


# We currently only return frequency bands that do not depend on the array
# assembly, so we just use AA0.5 as a constant. As the configuration API
# expands we will need to return results for different assemblys.
ARRAY_ASSEMBLY = "AA0.5"


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
    mid_response = get_osd(
        array_assembly=ARRAY_ASSEMBLY, capabilities="mid", source="car"
    )
    receiver_information = mid_response["capabilities"]["mid"]["basic_capabilities"][
        "receiver_information"
    ]
    return MidConfiguration(
        frequency_band=[
            FrequencyBand(**reciever_info) for reciever_info in receiver_information
        ]
    )


def _get_low_telescope_configuration() -> LowConfiguration:
    low_response = get_osd(
        array_assembly=ARRAY_ASSEMBLY, capabilities="low", source="car"
    )
    receiver_information = low_response["capabilities"]["low"]["basic_capabilities"]
    return LowConfiguration(frequency_band=FrequencyBand(**receiver_information))
