"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from functools import cache
from importlib.metadata import version
from typing import Union

from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm._shared.spfrx import (
    NoiseDiodeMode,
    PeriodicNoiseDiodeConfig,
    PseudoRandomNoiseDiodeConfig,
    SPFRxNoiseDiodeDurationUnits,
    TargetSPFRxConfiguration,
)
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import CSPSPFRxConfiguration, ReceiverBand
from ska_ost_osd.osd.models.capabilities import Band5bSubband, MidFrequencyBand
from ska_ost_osd.osd.models.configuration import Configuration
from ska_ost_osd.osd.models.defaults import SyncPPS
from ska_telmodel_client import TMData

# tmdata's default noise diode mode is a tri-state string ("periodic",
# "pseudo_random", "off"), but PDM's NoiseDiodeMode enum only covers the first
# two - PDM already models "no noise diode" as `noise_diode=None` rather than
# a third mode - so "off" is handled separately below.
NOISE_DIODE_MODE_OFF = "off"

OSD_VERSION = version("ska-ost-osd")


@cache
def configuration_from_osd(osd_version: str = OSD_VERSION) -> Configuration:
    """
    Builds the Configuration for the UI from the OSD's tmdata.
    """
    tmdata = TMData([f"car:ost/ska-ost-osd?{osd_version}"], update=True)
    return Configuration.from_tmdata(tmdata)


def get_telescope_observing_constraint(telescope: TelescopeType, parameter: str):
    """
    Utility function to extract an observing constraint from the OSD
    """
    osd = configuration_from_osd()
    if telescope == TelescopeType.SKA_MID:
        constraints = osd.ska_mid.constraints
    else:
        constraints = osd.ska_low.constraints

    if parameter not in type(constraints).model_fields:
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

    if parameter not in type(subarray).model_fields:
        raise ValueError(
            f"{parameter} is not available for validation for "
            f"{telescope.value} array assembly {validation_array_assembly.value}"
        )

    return getattr(subarray, parameter)


def get_default_pdm_target_spfrx() -> TargetSPFRxConfiguration:
    target_spfrx = configuration_from_osd().ska_mid.spfrx_defaults.target_spfrx
    default_mode = target_spfrx.default_noise_diode_mode

    valid_modes = [NOISE_DIODE_MODE_OFF, *(m.value for m in NoiseDiodeMode)]
    if default_mode not in valid_modes:
        raise ValueError(
            f"default noise diode mode {default_mode} is not supported, "
            f"options are {', '.join(valid_modes)}, please update the tmdata "
            "file accordingly"
        )

    options_by_mode = {option.mode.value: option for option in target_spfrx.noise_diode_options}
    diode = None if default_mode == NOISE_DIODE_MODE_OFF else options_by_mode[default_mode]

    data = target_spfrx.model_dump(exclude={"noise_diode_options", "default_noise_diode_mode"})
    data["noise_diode"] = _noise_diode_osd_to_pdm(diode)

    return TargetSPFRxConfiguration(**data)


def _noise_diode_osd_to_pdm(diode):
    """
    Private function that maps the non quantity OSD noise diode option to a PDM
    noise diode config model, converting `*_ms` fields to the {"value", "unit"}
    dicts that PDM's Quantity fields validate directly.
    """
    if diode is None:
        return None

    converted = {}
    for field, value in diode.model_dump().items():
        if field.endswith("_ms"):
            converted[field.removesuffix("_ms")] = {
                "value": value,
                "unit": SPFRxNoiseDiodeDurationUnits.MILLISECONDS,
            }
        else:
            converted[field] = value

    if diode.mode == NoiseDiodeMode.PERIODIC:
        return PeriodicNoiseDiodeConfig(**converted)
    if diode.mode == NoiseDiodeMode.PSEUDO_RANDOM:
        return PseudoRandomNoiseDiodeConfig(**converted)
    raise ValueError(f"no config mapping for noise diode mode {diode.mode!r}")


def get_defaults_pdm_csp_spfrx() -> CSPSPFRxConfiguration:
    csp_spfrx = configuration_from_osd().ska_mid.spfrx_defaults.csp_spfrx
    return CSPSPFRxConfiguration(
        sync_pps=_sync_pps_osd_to_pdm(csp_spfrx.sync_pps),
        saturation_threshold=csp_spfrx.saturation_threshold,
    )


def _sync_pps_osd_to_pdm(sync_pps: SyncPPS) -> bool | None:
    """
    Private function that maps the OSD's tri-state sync_pps value to the
    bool/None of PDM's CSPSPFRxConfiguration.sync_pps.
    """
    return {SyncPPS.ON: True, SyncPPS.OFF: False, SyncPPS.UNSET: None}[sync_pps]
