"""
Model specific for the pht
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field
from ska_oso_pdm.proposal import ProposalAccess, ProposalPermissions, ProposalRole

from ska_oso_services.common.model import AppModel


class PrslRole(str, Enum):
    """
    Enum containing the IDs of PHT specific role-granting Groups
    defined in MS Entra ID.
    """

    # obs-oauth2role-opsproposaladmin
    # Individual who is able to perform all activities associated with proposals
    OPS_PROPOSAL_ADMIN = "ce3627de-8ec2-4a35-ab1e-300eec6a0a50"

    # obs-oauth2role-scireviewer
    # Individual who is able to provide a review of the science behind a proposal
    SCIENCE_REVIEWER = "05883c37-b723-4b63-9216-0a789a61cb07"

    # obs-oauth2role-tecreviewer
    # Individual who is able to validate the feasibility of the
    # technical aspects required
    # for a proposal
    TECHNICAL_REVIEWER = "4c45b2ea-1b56-4b2d-b209-8d970b4e39dc"

    # obs-oauth2role-opsreviewerchair
    # Individual who is able to make the final decision on the acceptance
    # of a submission taking into account all technical and scientific reviews
    OPS_REVIEW_CHAIR = "2670cf1b-8688-47c7-bf97-674eb7bf0043"

    def __str__(self):
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}(gid={self.value!r})"


class EmailRequest(AppModel):
    """
    Schema for incoming email request.

    Attributes:
        email (EmailStr): The recipient's email address.
        prsl_id (str): The SKAO proposal ID.
    """

    email: EmailStr
    prsl_id: str


class ProposalAccessResponse(AppModel):
    prsl_id: str = None
    role: ProposalRole
    permissions: list[ProposalPermissions] = Field(
        ..., description="Permissions granted to this user for this proposal."
    )


class ProposalAccessByProposalResponse(ProposalAccessResponse):
    access_id: str
    user_id: str


class ProposalAccessCreate(ProposalAccess):
    access_id: Optional[str] = None


class PanelCreateResponse(AppModel):
    panel_id: str
    name: str
    proposal_count: int


class PanelCreate(AppModel):
    name: str
    reviewers: list
    proposals: list


class CycleInformation(BaseModel):
    cycle_id: str
    proposal_open: str
    proposal_close: str


class CyclePolicies(BaseModel):
    normal_max_hours: int
    max_targets: Optional[int] = None
    max_observation_setups: Optional[int] = None
    max_data_products: Optional[int] = None


class TelescopeCapabilities(BaseModel):
    Mid: Optional[str] = None
    Low: Optional[str] = None


class ObservatoryPolicy(BaseModel):
    cycle_number: int
    cycle_id: Optional[str] = None
    type: Optional[str] = None
    cycle_description: str
    cycle_information: CycleInformation
    cycle_policies: CyclePolicies
    telescope_capabilities: TelescopeCapabilities


class ReceiverInformation(BaseModel):
    rx_id: str
    min_frequency_hz: int
    max_frequency_hz: int
    sub_bands: list[dict] | None = None


class BasicCapabilitiesMid(BaseModel):
    dish_elevation_limit_deg: int
    receiver_information: list[ReceiverInformation]


class AA2_MID(BaseModel):
    allowed_channel_count_range_max: list[int]
    allowed_channel_count_range_min: list[int]
    allowed_channel_width_values: list[int]
    available_receivers: list[str]
    number_ska_dishes: int
    number_meerkat_dishes: int
    number_meerkatplus_dishes: int
    max_baseline_km: int
    available_bandwidth_hz: int
    number_channels: int | None = None
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
    channel_width_hz: Optional[float] = None
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
    mid: Optional[Mid] = None
    low: Optional[Low] = None


class OsdDataModel(BaseModel):
    observatory_policy: ObservatoryPolicy
    capabilities: Capabilities
