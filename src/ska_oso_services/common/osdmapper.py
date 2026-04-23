"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from functools import cache
from importlib.metadata import version
from typing import Union

from pydantic import AliasChoices, BaseModel, Field, dataclasses
from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand
from ska_ost_osd.osd.common.error_handling import OSDModelError
from ska_ost_osd.osd.models.models import OSDQueryParams
from ska_ost_osd.osd.routers.api import get_cycle_list, get_osd

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


class Subarray(BaseModel):
    name: str
    receptors: list[str | int] = Field(
        validation_alias=AliasChoices("number_dish_ids", "number_station_ids")
    )
    available_bandwidth_hz: float
    number_pst_beams: int
    number_fsps: int


class MidSubarray(Subarray):
    allowed_channel_width_values_hz: list[int]


class LowSubarray(Subarray):
    number_substations: int
    number_subarray_beams: int


@dataclasses.dataclass
class Constraints:
    sun_avoidance_angle_deg: float
    moon_avoidance_angle_deg: float
    jupiter_avoidance_angle_deg: float
    min_elevation_deg: float
    max_elevation_deg: float


class CbfMetrics(AppModel):
    alveo_configured_percent: float


class LowQualityAttributeMetrics(AppModel):
    cbf: CbfMetrics


class MidQualityAttributeMetrics(AppModel):
    pass


class MidConfiguration(AppModel):
    frequency_band: list[MidFrequencyBand]
    constraints: Constraints
    quality_attribute_metrics: MidQualityAttributeMetrics | None
    subarrays: list[Subarray]


class LowConfiguration(AppModel):
    frequency_band: LowFrequencyBand
    constraints: Constraints
    quality_attribute_metrics: LowQualityAttributeMetrics
    subarrays: list[LowSubarray]


class Configuration(AppModel):
    ska_mid: MidConfiguration
    ska_low: LowConfiguration


@cache
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

    mid_response = get_osd_data(capabilities="mid", source=OSD_SOURCE, osd_version=OSD_VERSION)[
        "capabilities"
    ]["mid"]

    subarrays = [
        MidSubarray(
            name=array_assembly,
            **mid_response[array_assembly],
        )
        for array_assembly in SUPPORTED_COMMON_ARRAY_ASSEMBLIES + MID_ARRAY_ASSEMBLIES
    ]

    quality_attribute_metrics = mid_response.get("quality_attribute_metrics", {})

    receiver_information = mid_response["basic_capabilities"]["receiver_information"]
    constraints = mid_response["constraints"]

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
        quality_attribute_metrics=MidQualityAttributeMetrics(**quality_attribute_metrics),
        constraints=Constraints(**constraints),
        subarrays=subarrays,
    )


def _get_low_telescope_configuration() -> LowConfiguration:

    low_response = get_osd_data(capabilities="low", source=OSD_SOURCE, osd_version=OSD_VERSION)[
        "capabilities"
    ]["low"]

    subarrays = [
        LowSubarray(
            name=array_assembly,
            **low_response[array_assembly],
        )
        for array_assembly in SUPPORTED_COMMON_ARRAY_ASSEMBLIES + LOW_ARRAY_ASSEMBLIES
    ]

    quality_attribute_metrics = low_response.get("quality_attribute_metrics", {})

    receiver_information = low_response["basic_capabilities"]
    constraints = low_response["constraints"]

    return LowConfiguration(
        frequency_band=LowFrequencyBand(**receiver_information),
        constraints=Constraints(**constraints),
        quality_attribute_metrics=LowQualityAttributeMetrics(**quality_attribute_metrics),
        subarrays=subarrays,
    )


@cache
def get_osd_cycles():
    """
    Wrapper function for `get_cycle_list` that fetches osd data

    This function calls `get_cycle_list`,
    and returns the result data. If `get_cycle_list` raises an `OSDModelError` or
    `ValueError`, this function wraps and raises it as an `OSDError`
    """
    try:
        osd_data = get_cycle_list()
    except (OSDModelError, ValueError) as error:
        raise OSDError(error)
    data = osd_data.model_dump()["result_data"] if hasattr(osd_data, "model_dump") else osd_data
    return data


@cache
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


def get_telescope_observing_constraint(telescope: TelescopeType, parameter: str):
    """
    Utility function to extract an observing constraint from the OSD
    """
    osd = configuration_from_osd()
    if telescope == TelescopeType.SKA_MID:
        constraints = osd.ska_mid.constraints
    else:
        constraints = osd.ska_low.constraints

    if not hasattr(constraints, parameter):
        raise ValueError(f"{parameter} is not a valid observing constraint for {telescope.value}")

    return getattr(constraints, parameter)


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
        raise ValueError(f"Cannot specify and band 5b subband for band {obs_band}")
    elif obs_band == ReceiverBand.BAND_5B and band5b_subband is None:
        raise ValueError("Band 5b subband must be specified for band 5b observation")

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
        raise ValueError(f"Invalid telescope: {telescope.value}")

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
