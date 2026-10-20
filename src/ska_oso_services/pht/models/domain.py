"""
Model specific for the pht
"""

from enum import StrEnum
from typing import Optional

from pydantic import EmailStr, Field
from ska_oso_pdm.proposal import ProposalAccess, ProposalPermissions, ProposalRole

from ska_oso_services.common.model import AppModel


class PrslRole(StrEnum):
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
