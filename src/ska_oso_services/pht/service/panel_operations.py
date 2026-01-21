import logging
from datetime import datetime, timezone
from typing import Iterable

from ska_db_oda.repository.domain import ODANotFound
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm import PanelDecision, PanelReview
from ska_oso_pdm.proposal.proposal import Proposal, ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel, ProposalAssignment
from ska_oso_pdm.proposal_management.review import (
    Conflict,
    ReviewStatus,
    ScienceReview,
    TechnicalReview,
)

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.models.schemas import PanelAssignResponse
from ska_oso_services.pht.utils.pht_helper import generate_entity_id, get_latest_entity_by_id

logger = logging.getLogger(__name__)


def build_assignment_response(updates: dict[str, tuple[Panel, int]]) -> list[PanelAssignResponse]:
    """Convert name -> (panel, added_count) to response list."""
    return [
        PanelAssignResponse(
            panel_id=panel.panel_id,
            name=name,
            proposals_added=added,
            total_proposals_after=len(panel.proposals or []),
        )
        for name, (panel, added) in updates.items()
    ]


def build_sv_panel_proposals(submitted_proposals: list) -> list[ProposalAssignment]:
    """Typed assignments for the Science Verification panel."""
    assigned_at_utc = datetime.now(timezone.utc)
    return [
        ProposalAssignment(prsl_id=ref_proposal.prsl_id, assigned_on=assigned_at_utc)
        for ref_proposal in submitted_proposals
    ]


def group_proposals_by_science_category(
    proposals: list, allowed_panel_names: list[str]
) -> dict[str, list]:
    """
    Group proposals by info.science_category. Only include categories
    in allowed_panel_names. Skip unmatched categories and log warnings.

    The science_category is defined here as constants for now but should come from OSD.
    Note: Any additional rules needed to auto-generate panels can be added here as well.
    """
    grouped_by_category: dict[str, list] = {name: [] for name in allowed_panel_names}
    skipped_count = 0

    for proposal in proposals:
        info = getattr(proposal, "info", None)
        category = (
            info.get("science_category")
            if isinstance(info, dict)
            else getattr(info, "science_category", None)
        )
        if category not in grouped_by_category:
            skipped_count += 1
            logger.warning(
                "Skipping proposal '%s' (science_category '%s' not in panel list)",
                getattr(proposal, "prsl_id", "?"),
                category,
            )
            continue
        grouped_by_category[category].append(proposal)

    if skipped_count:
        logger.warning(
            "%d proposals skipped due to missing/invalid science_category.",
            skipped_count,
        )

    return grouped_by_category


def assign_to_existing_panel(
    *,
    uow,
    auth,
    panel: Panel,
    proposals: Iterable,
    sci_reviewers: list | None,
    tech_reviewers: list | None,
) -> tuple[Panel, int, list[str]]:
    """
    Assign only to an existing panel; never create.
    Returns (persisted_panel, added_count, added_prsl_ids).

    NOTE: Does NOT change proposal statuses.
    """
    # Overwrite reviewers only if provided
    if sci_reviewers is not None:
        panel.sci_reviewers = sci_reviewers
    if tech_reviewers is not None:
        panel.tech_reviewers = tech_reviewers

    existing_ids = {
        (e["prsl_id"] if isinstance(e, dict) else getattr(e, "prsl_id", None))
        for e in (panel.proposals or [])
    }

    assigned_at = datetime.now(timezone.utc)
    to_add_assignments: list[ProposalAssignment] = []
    to_add_ids: list[str] = []

    for inc in proposals or []:
        prsl_id = getattr(inc, "prsl_id", None)
        if not prsl_id or prsl_id in existing_ids:
            continue
        to_add_assignments.append(ProposalAssignment(prsl_id=prsl_id, assigned_on=assigned_at))
        to_add_ids.append(prsl_id)

    if to_add_assignments:
        panel.proposals = (panel.proposals or []) + to_add_assignments

    persisted: Panel = uow.panels.add(panel, auth.user_id)
    return persisted, len(to_add_assignments), to_add_ids


def ensure_submitted_proposals_under_review(uow, auth, prsl_ids: Iterable[str]) -> None:
    seen: set[str] = set()
    for raw in prsl_ids:
        prsl_id = str(raw).strip()
        if not prsl_id or prsl_id in seen:
            continue
        seen.add(prsl_id)

        try:
            proposal: Proposal = uow.prsls.get(prsl_id)
        except ODANotFound as exc:
            raise BadRequestError(f"Proposal '{prsl_id}' does not exist") from exc

        if proposal.status != ProposalStatus.UNDER_REVIEW:
            proposal.status = ProposalStatus.UNDER_REVIEW
            uow.prsls.add(proposal, auth.user_id)  # type: ignore[attr-defined]


def ensure_review_exist_or_create(
    uow, param, kind: str, reviewer_id: str, proposal_id: str
) -> str:
    """
    Ensure a review of the given kind exists for the given proposal and reviewer.
    If not, create one with status TO_DO and return its review_id.
    """
    query = CustomQuery(prsl_id=proposal_id, kind=kind, reviewer_id=reviewer_id)
    existing = get_latest_entity_by_id(uow.rvws.query(query), "review_id")
    existing_rvw = existing[0] if existing else None

    if existing_rvw:  # TODO: check for where the metadata version ==1
        logger.debug(
            "%s already exists (prsl_id=%s, reviewer=%s)",
            kind,
            proposal_id,
            existing_rvw.reviewer_id,
        )
        return existing_rvw.review_id

    if kind == "Technical Review":
        review_type = TechnicalReview(kind="Technical Review")
    else:
        review_type = ScienceReview(kind="Science Review", conflict=Conflict(has_conflict=False))

    new_review = PanelReview(
        panel_id=param.panel_id,
        review_id=generate_entity_id("rvw-tec" if kind == "Technical Review" else "rvw-sci"),
        reviewer_id=reviewer_id,
        cycle=param.cycle,
        prsl_id=proposal_id,
        status=ReviewStatus.TO_DO,
        review_type=review_type,
    )
    created_rvw = uow.rvws.add(new_review)
    logger.info("Creating %s (prsl_id=%s, reviewer=%s)", kind, proposal_id, reviewer_id)
    return created_rvw.review_id


def ensure_decision_exist_or_create(uow, param, proposal_id: str) -> str:
    """
    Ensure a decision exists for the given proposal.
    If not, create one with status TO_DO and return its decision_id.
    """
    query = CustomQuery(prsl_id=proposal_id)
    existing = get_latest_entity_by_id(uow.pnlds.query(query), "decision_id")
    existing_pnld = existing[0] if existing else None

    if existing_pnld and hasattr(existing_pnld, "decision_id"):
        logger.debug(
            "%s already exists (prsl_id=%s)",
            proposal_id,
            existing_pnld.decision_id,
        )
        return existing_pnld.decision_id

    new_review = PanelDecision(
        panel_id=param.panel_id,
        decision_id=generate_entity_id("pnld"),
        cycle=param.cycle,
        prsl_id=proposal_id,
    )
    created_pnld: PanelDecision = uow.pnlds.add(new_review)
    logger.info("Creating decision %s (prsl_id=%s)", created_pnld.decision_id, proposal_id)
    return created_pnld.decision_id
