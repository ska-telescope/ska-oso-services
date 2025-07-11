"""
Model specific for the pht
"""

from typing import List

from pydantic import EmailStr

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


class ProposalReport(AppModel):
    prsl_id: str
    title: str
    science_category: str | None = None
    proposal_status: str
    proposal_type: str
    cycle: str
    proposal_attributes: List[str]
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
    review_submitted_on: str | None = None
    decision_on: str | None = None
    decision_status: str | None = None
