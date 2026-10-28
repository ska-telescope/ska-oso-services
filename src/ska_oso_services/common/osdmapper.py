"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from functools import cache

from ska_oso_pdm import TelescopeType
from ska_oso_pdm._shared.spfrx import (
    NoiseDiodeMode,
    PeriodicNoiseDiodeConfig,
    PseudoRandomNoiseDiodeConfig,
    SPFRxNoiseDiodeDurationUnits,
    TargetSPFRxConfiguration,
)
from ska_oso_pdm.sb_definition.csp.midcbf import CSPSPFRxConfiguration
from ska_ost_osd.osd.adapters.tmdata import TMDataRepository
from ska_ost_osd.osd.common.constant import Telescope
from ska_ost_osd.osd.models.defaults import SyncPPS
from ska_ost_osd.osd.views.odt import Configuration, get_configuration
from ska_telmodel_client import TMData

# tmdata's default noise diode mode is a tri-state string ("periodic",
# "pseudo_random", "off"), but PDM's NoiseDiodeMode enum only covers the first
# two - PDM already models "no noise diode" as `noise_diode=None` rather than
# a third mode - so "off" is handled separately below.
NOISE_DIODE_MODE_OFF = "off"

OSD_VERSION = "7.0.0"
OSD_CYCLES_SOURCE = "gitlab://gitlab.com/ska-telescope/ost/ska-ost-osd?5e5f8dbe#tmdata"

OSD_TELESCOPES = {TelescopeType.SKA_MID: Telescope.MID, TelescopeType.SKA_LOW: Telescope.LOW}


@cache
def osd_repository(osd_version: str = OSD_VERSION) -> TMDataRepository:
    """
    The OSD repository, reading the OSD's tmdata.
    """
    tmdata = TMData([OSD_CYCLES_SOURCE, f"car:ost/ska-ost-osd?{osd_version}"], update=True)
    return TMDataRepository(tmdata)


@cache
def configuration_from_osd() -> Configuration:
    """
    Builds the Configuration for the UI from the OSD.
    """
    return get_configuration(osd_repository())


def get_default_pdm_target_spfrx() -> TargetSPFRxConfiguration:
    target_spfrx = osd_repository().get_defaults(Telescope.MID).spfrx_defaults.target_spfrx
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
    csp_spfrx = osd_repository().get_defaults(Telescope.MID).spfrx_defaults.csp_spfrx
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
