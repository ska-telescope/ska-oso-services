"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from importlib.metadata import version
from typing import Union

from pydantic import dataclasses
from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand
from ska_ost_osd.osd.common.error_handling import OSDModelError
from ska_ost_osd.osd.models.models import OSDQueryParams
from ska_ost_osd.osd.routers.api import get_osd

from ska_oso_services.common.error_handling import OSDError
from ska_oso_services.common.model import AppModel

SUPPORTED_COMMON_ARRAY_ASSEMBLIES = ["AA0.5", "AA1", "AA2"]
MID_ARRAY_ASSEMBLIES = ["Mid_ITF"]
LOW_ARRAY_ASSEMBLIES = ["AA2_SV", "Low_ITF"]

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


@dataclasses.dataclass
class MidFrequencyBand(FrequencyBand):
    rx_id: str
    band5b_subbands: list[Band5bSubband] | None = None


@dataclasses.dataclass
class LowFrequencyBand(FrequencyBand):
    min_coarse_channel: int
    max_coarse_channel: int
    coarse_channel_width_hz: float
    number_continuum_channels_per_coarse_channel: int
    number_zoom_channels_per_coarse_channel: int


@dataclasses.dataclass
class Subarray:
    name: str
    receptors: list[str | int]
    available_bandwidth_hz: float
    number_pst_beams: int
    number_fsps: int


@dataclasses.dataclass
class MidSubarray(Subarray):
    allowed_channel_width_values_hz: list[int]


@dataclasses.dataclass
class LowSubarray(Subarray):
    number_substations: int
    number_subarray_beams: int


class MidConfiguration(AppModel):
    frequency_band: list[MidFrequencyBand]
    subarrays: list[Subarray]


class LowConfiguration(AppModel):
    frequency_band: LowFrequencyBand
    subarrays: list[LowSubarray]


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
    for array_assembly in SUPPORTED_COMMON_ARRAY_ASSEMBLIES + MID_ARRAY_ASSEMBLIES:
        mid_response = get_osd_data(
            array_assembly=array_assembly,
            capabilities="mid",
            source=OSD_SOURCE,
            osd_version=OSD_VERSION,
        )
        subarrays.append(
            MidSubarray(
                name=array_assembly,
                receptors=mid_response["capabilities"]["mid"][array_assembly]["number_dish_ids"],
                available_bandwidth_hz=mid_response["capabilities"]["mid"][array_assembly][
                    "available_bandwidth_hz"
                ],
                allowed_channel_width_values_hz=mid_response["capabilities"]["mid"][
                    array_assembly
                ]["allowed_channel_width_values"],
                number_pst_beams=mid_response["capabilities"]["mid"][array_assembly][
                    "number_pst_beams"
                ],
                number_fsps=mid_response["capabilities"]["mid"][array_assembly]["number_fsps"],
            )
        )

    # Receiver information is the same for each array assembly, as such we use the
    # last fetched response to populate this information.

    receiver_information = mid_response["capabilities"]["mid"]["basic_capabilities"][
        "receiver_information"
    ]

    def frequency_band_from_receiver_information_for_band(receiver_information):
        band5b_subbands = (
            [Band5bSubband(**sub_band) for sub_band in receiver_information["sub_bands"]]
            if receiver_information["rx_id"] == "Band_5b"
            else None
        )

        return MidFrequencyBand(**receiver_information, band5b_subbands=band5b_subbands)

    return MidConfiguration(
        frequency_band=[
            frequency_band_from_receiver_information_for_band(receiver_info)
            for receiver_info in receiver_information
        ],
        subarrays=subarrays,
    )


def _get_low_telescope_configuration() -> LowConfiguration:
    subarrays = []
    for array_assembly in SUPPORTED_COMMON_ARRAY_ASSEMBLIES + LOW_ARRAY_ASSEMBLIES:
        low_response = get_osd_data(
            array_assembly=array_assembly,
            capabilities="low",
            source=OSD_SOURCE,
            osd_version=OSD_VERSION,
        )
        subarrays.append(
            LowSubarray(
                name=array_assembly,
                receptors=low_response["capabilities"]["low"][array_assembly][
                    "number_station_ids"
                ],
                available_bandwidth_hz=low_response["capabilities"]["low"][array_assembly][
                    "available_bandwidth_hz"
                ],
                number_pst_beams=low_response["capabilities"]["low"][array_assembly][
                    "number_pst_beams"
                ],
                number_fsps=low_response["capabilities"]["low"][array_assembly]["number_fsps"],
                number_substations=low_response["capabilities"]["low"][array_assembly][
                    "number_substations"
                ],
                number_subarray_beams=low_response["capabilities"]["low"][array_assembly][
                    "number_beams"
                ],
            )
        )

    receiver_information = low_response["capabilities"]["low"]["basic_capabilities"]

    # the following is a hack because I missed that the key in the OSD
    # should have included `_hz`

    additional_parameters = {
        "coarse_channel_width_hz": receiver_information["coarse_channel_width"]
    }
    receiver_information = {**receiver_information, **additional_parameters}

    return LowConfiguration(
        frequency_band=LowFrequencyBand(**receiver_information), subarrays=subarrays
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
    data = osd_data.model_dump()["result_data"] if hasattr(osd_data, "model_dump") else osd_data
    return data


def get_low_basic_capability_parameter_from_osd(parameter: str):
    """
    Utility function to extract one of the SKA Low basic capabilities from the OSD
    """
    osd = configuration_from_osd()

    telescope_osd = osd.ska_low.frequency_band
    if not hasattr(telescope_osd, parameter):
        raise ValueError(f"{parameter} is not available for validation for SKA Low")

    return getattr(telescope_osd, parameter)


def get_mid_frequency_band_data_from_osd(
    obs_band: ReceiverBand, band5b_subband: Union[pdm_Band5bSubband, None] = None
) -> Union[MidFrequencyBand, Band5bSubband]:
    """
    Utility function to extract SKA Mid frequency band data from the OSD
    """
    if obs_band != ReceiverBand.BAND_5B and band5b_subband is not None:
        raise ValueError(f"cannot specify and band 5b subband for band {obs_band}")
    elif obs_band == ReceiverBand.BAND_5B and band5b_subband is None:
        raise ValueError("band 5b subband must be specified for band 5b observation")

    osd = configuration_from_osd()
    bands = osd.ska_mid.frequency_band

    if band5b_subband is None:
        band_info = next(band for band in bands if band.rx_id == "Band_" + obs_band.value)

    else:
        subbands_info = next(
            band for band in bands if band.rx_id == "Band_" + obs_band.value
        ).band5b_subbands
        band_info = next(
            subband for subband in subbands_info if subband.sub_band == band5b_subband.value
        )

    return band_info


def get_subarray_specific_parameter_from_osd(
    telescope: TelescopeType,
    validation_array_assembly: Union[ValidationArrayAssembly, SubArrayMID, SubArrayLOW],
    parameter: str,
):
    """
    utility function to extract subarray specific parameters from the OSD
    """
    osd = configuration_from_osd()

    if not hasattr(osd, telescope.value):
        raise ValueError(f"invalid telescope: {telescope.value}")

    telescope_osd = getattr(osd, telescope.value)

    # extracting the subarray from the OSD
    subarray = next(
        (
            subarray
            for subarray in telescope_osd.subarrays
            if subarray.name == validation_array_assembly.value
        ),
        None,
    )

    if not subarray:
        raise ValueError(
            f"Invalid validation array assembly {validation_array_assembly} "
            f"for {telescope.value}"
        )

    if not hasattr(subarray, parameter):
        raise ValueError(
            f"{parameter} is not available for validation for "
            f"{telescope.value} array assembly {validation_array_assembly.value}"
        )

    return getattr(subarray, parameter)
