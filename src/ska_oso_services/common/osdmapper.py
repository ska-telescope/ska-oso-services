"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

import copy
from functools import cache
from importlib.metadata import version
from typing import Union

from pydantic import AliasChoices, BaseModel, Field, dataclasses
from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm._shared.spfrx import (
    NoiseDiodeMode,
    TargetSPFRxConfiguration,
)
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import CSPSPFRxConfiguration, ReceiverBand
from ska_ost_osd.osd.common.error_handling import OSDModelError
from ska_ost_osd.osd.models.models import OSDQueryParams
from ska_ost_osd.osd.routers.api import get_cycle_list, get_osd
from ska_telmodel_client import TMData

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
    number_pst_channels_per_coarse_channel: int
    number_pss_channels_per_coarse_channel: int


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


class Constraints(BaseModel):
    sun_avoidance_angle_deg: float
    moon_avoidance_angle_deg: float
    jupiter_avoidance_angle_deg: float
    min_elevation_deg: float
    max_elevation_deg: float


class PeriodicNoiseDiode(BaseModel):
    mode: str = NoiseDiodeMode.PERIODIC
    period_ms: float
    duty_cycle_ms: float
    phase_shift_ms: float


class PseudoRandomNoiseDiode(BaseModel):
    mode: str = NoiseDiodeMode.PSEUDO_RANDOM
    binary_polynomial: int
    seed: int
    dwell_ms: float

class TargetSPFRx (TargetSPFRxConfiguration):
    noise_diode_options: list[PeriodicNoiseDiode | PseudoRandomNoiseDiode]


class SPFRxParameters(BaseModel):
    target_spfrx: TargetSPFRx
    csp_spfrx: CSPSPFRxConfiguration


@dataclasses.dataclass
class LowCBFMetrics:
    processors_ready_percent: float


@dataclasses.dataclass
class LowQualityAttributeMetrics:
    cbf: LowCBFMetrics


class MidConfiguration(AppModel):
    frequency_band: list[MidFrequencyBand]
    constraints: Constraints
    subarrays: list[Subarray]
    spfrx_defaults: SPFRxParameters


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
    tmdata = get_osd_tmdata()
    return Configuration(
        ska_mid=_get_mid_telescope_configuration(tmdata=tmdata),
        ska_low=_get_low_telescope_configuration(tmdata=tmdata),
    )


def _get_mid_telescope_configuration(tmdata: TMData) -> MidConfiguration:

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

    receiver_information = mid_response["basic_capabilities"]["receiver_information"]

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
        constraints=_get_telescope_constraints(telescope=TelescopeType.SKA_MID, tmdata=tmdata),
        subarrays=subarrays,
        spfrx_defaults=_get_spfrx_defaults(tmdata=tmdata),
    )


def _get_low_telescope_configuration(tmdata: TMData) -> LowConfiguration:

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

    quality_attribute_metrics = low_response["quality_attribute_metrics"]
    receiver_information = low_response["basic_capabilities"]

    return LowConfiguration(
        frequency_band=LowFrequencyBand(**receiver_information),
        constraints=_get_telescope_constraints(telescope=TelescopeType.SKA_LOW, tmdata=tmdata),
        quality_attribute_metrics=LowQualityAttributeMetrics(**quality_attribute_metrics),
        subarrays=subarrays,
    )


def _get_telescope_constraints(telescope: TelescopeType, tmdata: TMData) -> Constraints:
    if telescope == TelescopeType.SKA_MID:
        path_prefix = "ska1_mid/mid_"
    else:
        path_prefix = "ska1_low/low_"

    default_constraints_dict = tmdata[f"{path_prefix}defaults.json"].get_dict()["constraints"]
    capabilities_constraints_dict = tmdata[f"{path_prefix}capabilities.json"].get_dict()[
        "constraints"
    ]

    constraints = Constraints(**{**capabilities_constraints_dict, **default_constraints_dict})

    return constraints


def _get_spfrx_defaults(tmdata: TMData) -> SPFRxParameters:
    defaults = tmdata["ska1_mid/mid_defaults.json"].get_dict()["defaults"]

    dish_spfrx_params = defaults["target"]["dish_spfrx_params"]
    noise_diode = dish_spfrx_params["noise_diode"]

    noise_diode_options = [
        PeriodicNoiseDiode(**noise_diode["periodic"]),
        PseudoRandomNoiseDiode(**noise_diode["pseudo_random"]),
    ]

    target_spfrx_params = {
        key: value for key, value in dish_spfrx_params.items() if key != "noise_diode"
    }

    return SPFRxParameters(
        target_spfrx=TargetSPFRx(**target_spfrx_params, noise_diode_options=noise_diode_options),
        csp_spfrx=CSPSPFRxConfiguration(**defaults["csp_configuration"]["spfrx"]),
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
def get_osd_tmdata():
    """
    Wrapper function to fetch tmdata from the OSD that is not integrated into the
    OSD source code
    """
    tmdata = TMData([f"car:ost/ska-ost-osd?{OSD_VERSION}"], update=True)
    return tmdata


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
            f"Invalid validation array assembly {validation_array_assembly} for {telescope.value}"
        )

    if not hasattr(subarray, parameter):
        raise ValueError(
            f"{parameter} is not available for validation for "
            f"{telescope.value} array assembly {validation_array_assembly.value}"
        )

    return getattr(subarray, parameter)
