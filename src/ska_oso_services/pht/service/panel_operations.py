import logging
from datetime import datetime, timezone
from typing import Iterable

from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal_management.panel import Panel, ProposalAssignment
from ska_oso_pdm.proposal.proposal import ProposalStatus, Proposal
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.models.schemas import PanelCreateResponse
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
)

logger = logging.getLogger(__name__)


def build_panel_response(panels_by_name: dict[str, Panel]) -> list[PanelCreateResponse]:
    """Build a summary for each panel: id, name, proposal_count."""
    return [
        PanelCreateResponse(
            panel_id=panel.panel_id,
            name=name,
            proposal_count=len(panel.proposals or []),
        )
        for name, panel in panels_by_name.items()
    ]


def build_sv_panel_proposals(submitted_proposals: list) -> list[ProposalAssignment]:
    """Typed assignments for the Science Verification panel."""
    assigned_at_utc = datetime.now(timezone.utc)
    return [
        ProposalAssignment(prsl_id=ref.prsl_id, assigned_on=assigned_at_utc)
        for ref in submitted_proposals
    ]


def group_proposals_by_science_category(
    proposals: list, allowed_panel_names: list[str]
) -> dict[str, list]:
    """
    Group proposals by info.science_category. Only include categories in allowed_panel_names.
    Skip unmatched categories and log warnings.
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
        logger.warning("%d proposals skipped due to missing/invalid science_category.", skipped_count)

    return grouped_by_category


def upsert_panel(
    *,
    uow,
    panel_name: str,
    science_reviewers: list | None,
    technical_reviewers: list | None,
    proposals: Iterable,  # Iterable[Proposal] (objects with .prsl_id/.status)
) -> Panel:
    """
    Existing panel:
      • For proposals already on the panel: if DB status != UNDER_REVIEW, update status and persist.
      • For new proposals: update status to UNDER_REVIEW, persist, and append a ProposalAssignment.

    No existing panel:
      • Create it; for all incoming proposals: update status to UNDER_REVIEW, persist, and add assignments.

    No commit here; caller controls the transaction.
    """
    assigned_at_utc = datetime.now(timezone.utc)

    existing_panels = get_latest_entity_by_id(
        uow.panels.query(CustomQuery(name=panel_name)), "panel_id"
    )
    panel: Panel | None = existing_panels[0] if existing_panels else None

    science_reviewers = science_reviewers or []
    technical_reviewers = technical_reviewers or []

    # Deduplicate incoming proposals by prsl_id (keep first occurrence)
    incoming_proposals_by_id: dict[str, Proposal] = {}
    for proposal in proposals or []:
        proposal_id = getattr(proposal, "prsl_id", None)
        if proposal_id and proposal_id not in incoming_proposals_by_id:
            incoming_proposals_by_id[proposal_id] = proposal

    if panel:
        # Helper to read proposal id from existing assignments (typed or legacy dict)
        def get_assignment_proposal_id(entry) -> str | None:
            return entry["prsl_id"] if isinstance(entry, dict) else getattr(entry, "prsl_id", None)

        existing_assignment_ids = {
            pid for entry in (panel.proposals or [])
            if (pid := get_assignment_proposal_id(entry))
        }

        # Already on panel → ensure UNDER_REVIEW in DB
        for proposal_id in existing_assignment_ids.intersection(incoming_proposals_by_id.keys()):
            db_proposal: Proposal = uow.prsls.get(proposal_id)
            if db_proposal and db_proposal.status != ProposalStatus.UNDER_REVIEW:
                db_proposal.status = ProposalStatus.UNDER_REVIEW
                uow.prsls.add(db_proposal)
                logger.info(
                    "Proposal %s set to UNDER_REVIEW (already in panel '%s')",
                    proposal_id, panel_name
                )
            incoming_proposals_by_id.pop(proposal_id, None)

        # New to panel → update status and append assignment
        for proposal_id, _incoming in incoming_proposals_by_id.items():
            db_proposal: Proposal = uow.prsls.get(proposal_id)
            if db_proposal and db_proposal.status != ProposalStatus.UNDER_REVIEW:
                db_proposal.status = ProposalStatus.UNDER_REVIEW
                uow.prsls.add(db_proposal)
                logger.info(
                    "Proposal %s set to UNDER_REVIEW and added to panel '%s'",
                    proposal_id, panel_name
                )

            panel.proposals.append(
                ProposalAssignment(prsl_id=proposal_id, assigned_on=assigned_at_utc)
            )

        return uow.panels.add(panel)

    # Create panel → update all incoming proposals and add assignments
    assignments: list[ProposalAssignment] = []
    for proposal_id, _incoming in incoming_proposals_by_id.items():
        db_proposal: Proposal = uow.prsls.get(proposal_id)
        if db_proposal and db_proposal.status != ProposalStatus.UNDER_REVIEW:
            db_proposal.status = ProposalStatus.UNDER_REVIEW
            uow.prsls.add(db_proposal)
            logger.info(
                "Proposal %s set to UNDER_REVIEW for new panel '%s'",
                proposal_id, panel_name
            )
        assignments.append(
            ProposalAssignment(prsl_id=proposal_id, assigned_on=assigned_at_utc)
        )

    new_panel = Panel(
        panel_id=generate_entity_id("panel"),
        name=panel_name,
        sci_reviewers=science_reviewers,
        tech_reviewers=technical_reviewers,
        proposals=assignments,
    )
    logger.info("Created panel '%s' with %d proposal(s)", panel_name, len(assignments))
    return uow.panels.add(new_panel)