"""
This module calls the OSD and converts the relevant parts into the
configuration needed for the application.
"""

from functools import cache

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
from ska_ost_osd.osd.models.capabilities import LowCapabilities, MidCapabilities
from ska_ost_osd.osd.models.defaults import SyncPPS
from ska_ost_osd.osd.views import odt
from ska_telmodel_client import TMData

from ska_oso_services.common.model import AppModel
from ska_oso_services.settings import get_settings

# tmdata's default noise diode mode is a tri-state string ("periodic",
# "pseudo_random", "off"), but PDM's NoiseDiodeMode enum only covers the first
# two - PDM already models "no noise diode" as `noise_diode=None` rather than
# a third mode - so "off" is handled separately below.
NOISE_DIODE_MODE_OFF = "off"

# (array assembly, policy) for each subarray the ODT serves, in the order it
# lists them. A subarray is named after its policy, or else its array assembly.
MID_SUBARRAYS: list[tuple[str, str | None]] = [
    ("AA0.5", None),
    ("AA1", None),
    ("AA2", None),
    ("Mid_ITF", None),
]
LOW_SUBARRAYS: list[tuple[str, str | None]] = [
    ("AA0.5", None),
    ("AA1", None),
    ("AA2", None),
    ("AA2", "AA2_SV"),
    ("Low_ITF", None),
]
SUBARRAYS = {Telescope.SKA_MID: MID_SUBARRAYS, Telescope.SKA_LOW: LOW_SUBARRAYS}


class MidConfiguration(AppModel):
    frequency_band: list[odt.MidFrequencyBand]
    constraints: odt.Constraints
    subarrays: list[odt.MidSubarray]
    spfrx_defaults: odt.SPFRxParameters


class LowConfiguration(AppModel):
    frequency_band: odt.LowFrequencyBand
    constraints: odt.Constraints
    quality_attribute_metrics: odt.LowQualityAttributeMetrics
    subarrays: list[odt.LowSubarray]


class Configuration(AppModel):
    """The ODT configuration: both telescopes' bands, constraints, defaults and subarrays."""

    ska_mid: MidConfiguration
    ska_low: LowConfiguration


@cache
def osd_repository() -> TMDataRepository:
    """
    The OSD repository, reading the OSD's tmdata from the sources in OSD_TMDATA,
    which the Helm chart sets from global.oso.osd_tmdata, by default OSD main in
    the CAR. It is read once per process, so a change to OSD_TMDATA, or to the
    data published for OSD main, needs a restart.
    """
    return TMDataRepository(TMData(get_settings().osd_tmdata, update=True))


def array_assembly_and_policy(telescope: Telescope, name: str) -> tuple[str, str | None]:
    """
    The OSD array assembly and policy of the subarray with a name, e.g. "AA2_SV"
    is the AA2 array assembly with the AA2_SV policy applied. A name that isn't
    one of the subarrays is taken as an array assembly with no policy.
    """
    for array_assembly, policy in SUBARRAYS[telescope]:
        if (policy or array_assembly) == name:
            return array_assembly, policy
    return name, None


def get_capabilities(telescope: Telescope, name: str) -> MidCapabilities | LowCapabilities:
    """
    The capabilities of the subarray with a name, e.g. a PDM
    ValidationArrayAssembly or SubArrayLOW value.

    :raises ArrayAssemblyNotFoundError: if the OSD has no such array assembly
    """
    return osd_repository().get_capabilities(
        telescope, *array_assembly_and_policy(telescope, name)
    )


def _odt_subarrays(telescope: Telescope) -> list[odt.MidSubarray] | list[odt.LowSubarray]:
    return [
        odt.get_subarray(osd_repository(), telescope, array_assembly, policy)
        for array_assembly, policy in SUBARRAYS[telescope]
    ]


@cache
def configuration_from_osd() -> Configuration:
    """
    Builds the Configuration for the ODT UI from the OSD's ODT view.
    """
    repository = osd_repository()
    return Configuration(
        ska_mid=MidConfiguration(
            frequency_band=odt.get_frequency_band(repository, Telescope.SKA_MID),
            constraints=odt.get_constraints(repository, Telescope.SKA_MID),
            subarrays=_odt_subarrays(Telescope.SKA_MID),
            spfrx_defaults=odt.get_spfrx_defaults(repository),
        ),
        ska_low=LowConfiguration(
            frequency_band=odt.get_frequency_band(repository, Telescope.SKA_LOW),
            constraints=odt.get_constraints(repository, Telescope.SKA_LOW),
            quality_attribute_metrics=odt.get_quality_attribute_metrics(repository),
            subarrays=_odt_subarrays(Telescope.SKA_LOW),
        ),
    )


def get_default_pdm_target_spfrx() -> TargetSPFRxConfiguration:
    target_spfrx = osd_repository().get_defaults(Telescope.SKA_MID).spfrx_defaults.target_spfrx
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
    csp_spfrx = osd_repository().get_defaults(Telescope.SKA_MID).spfrx_defaults.csp_spfrx
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
