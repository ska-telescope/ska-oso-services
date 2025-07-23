"""
Model specific for the pht
"""

from pydantic import BaseModel, EmailStr

from ska_oso_services.common.model import AppModel


class EmailRequest(AppModel):
    """
    Schema for incoming email request.

    Attributes:
        email (EmailStr): The recipient's email address.
        prsl_id (str): The SKAO proposal ID.
    """

    email: EmailStr
    prsl_id: str


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


class ProposalReport(AppModel):
    prsl_id: str
    title: str
    science_category: str | None = None
    proposal_status: str
    proposal_type: str
    cycle: str
    proposal_attributes: list[str]
    array: str
    panel_id: str | None = None
    panel_name: str | None = None
    reviewer_id: str | None = None
    reviewer_status: str | None = None
    review_status: str | None = None
    conflict: bool = False
    review_id: str | None = None
    review_rank: float | None = None
    comments: str | None = None
    review_status: str | None = None
    decision_id: str | None = None
    recommendation: str | None = None
    decision_status: str | None = None
    panel_rank: int | None = None
    panel_score: float | None = None
    review_submitted_on: str | None = None
    decision_on: str | None = None
    decision_status: str | None = None
