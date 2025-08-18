""" Schemas specific for the proposal handling tool (PHT) """

from pydantic import EmailStr, Field
from ska_oso_pdm.proposal import ProposalAccess, ProposalPermissions, ProposalRole

from ska_oso_services.common.model import AppModel


class EmailRequest(AppModel):
    """
    Schema for incoming email request.
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
    access_id: str | None = None


class PanelCreateResponse(AppModel):
    """Schema for response after creating a panel based on
    science categories and automatically assigning submitted proposals.
    """

    panel_id: str
    name: str
    proposal_count: int


class PanelCreateRequest(AppModel):
    """Schema for creating a new panel."""

    name: str
    reviewers: list[str] = Field(
        default_factory=list, description="List of reviewer entries.", example=[]
    )
    proposals: list[str] = Field(
        default_factory=list, description="List of proposal entries.", example=[]
    )


class ProposalReportResponse(AppModel):
    """Schema for proposal report response."""

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
    assigned_proposal: str | None = None
    recommendation: str | None = None
    decision_status: str | None = None
    panel_rank: int | None = None
    panel_score: float | None = None
    review_submitted_on: str | None = None
    decision_on: str | None = None
    decision_status: str | None = None
    country: str | None = None  # get the office location of the PI from entra id
