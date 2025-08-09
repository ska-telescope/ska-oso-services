"""
Model specific for the pht
"""

from pydantic import BaseModel


class CycleInformation(BaseModel):
    cycle_id: str
    proposal_open: str
    proposal_close: str


class CyclePolicies(BaseModel):
    normal_max_hours: int


class TelescopeCapabilities(BaseModel):
    Mid: str
    Low: str


class ObservatoryPolicy(BaseModel):
    cycle_number: int
    cycle_description: str
    cycle_information: CycleInformation
    cycle_policies: CyclePolicies
    telescope_capabilities: TelescopeCapabilities


class ReceiverInformation(BaseModel):
    rx_id: str
    min_frequency_hz: int
    max_frequency_hz: int


class BasicCapabilitiesMid(BaseModel):
    dish_elevation_limit_deg: int
    receiver_information: list[ReceiverInformation]


class AA2_MID(BaseModel):
    available_receivers: list[str]
    number_ska_dishes: int
    number_meerkat_dishes: int
    number_meerkatplus_dishes: int
    max_baseline_km: int
    available_bandwidth_hz: int
    number_channels: int
    cbf_modes: list[str]
    number_zoom_windows: int
    number_zoom_channels: int
    number_pss_beams: int
    number_pst_beams: int
    ps_beam_bandwidth_hz: int
    number_fsps: int


class Mid(BaseModel):
    basic_capabilities: BasicCapabilitiesMid
    AA2: AA2_MID


class BasicCapabilitiesLow(BaseModel):
    min_frequency_hz: int
    max_frequency_hz: int


class AA2_LOW(BaseModel):
    number_stations: int
    number_substations: int
    number_beams: int
    max_baseline_km: int
    available_bandwidth_hz: int
    channel_width_hz: int
    cbf_modes: list[str]
    number_zoom_windows: int
    number_zoom_channels: int
    number_pss_beams: int
    number_pst_beams: int
    number_vlbi_beams: int
    ps_beam_bandwidth_hz: int
    number_fsps: int


class Low(BaseModel):
    basic_capabilities: BasicCapabilitiesLow
    AA2: AA2_LOW


class Capabilities(BaseModel):
    mid: Mid
    low: Low


class OsdDataModel(BaseModel):
    observatory_policy: ObservatoryPolicy
    capabilities: Capabilities


