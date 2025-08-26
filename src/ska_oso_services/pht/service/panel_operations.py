import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from ska_db_oda.persistence.domain.errors import ODANotFound
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal.proposal import Proposal, ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel, ProposalAssignment

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.models.schemas import PanelCreateResponse
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
)

logger = logging.getLogger(__name__)


def build_panel_response(panels_by_name: dict[str, Panel]) -> list[PanelCreateResponse]:
    """
    Build a summary for each panel: id, name, proposal_count.
    This is used when a panels are created based on science categories.
    """
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


def upsert_panel(
    *,
    uow,
    panel_name: str,
    science_reviewers: list | None,
    technical_reviewers: list | None,
    proposals: Iterable,
) -> Panel:
    """
    Existing panel:
      • For proposals already on the panel:
          - If status != UNDER_REVIEW, set UNDER_REVIEW and persist
          --- just for extra caution.
      • For new proposals (by prsl_id comparison against existing assignments):
          - Append a ProposalAssignment first, then set status to
          UNDER_REVIEW and persist.

    No existing panel:
      • Create it; for every incoming proposal:
          - Append ProposalAssignment first, then set status to
          UNDER_REVIEW and persist.

    NOTE: No dedup of incoming proposals; the data model (PDM) handles this.
        The assumption here is that only Science Verification or Proposals
        and not both. We also need to update it here such that even when
        SV panel exist, it should use the OSD to determine the panel to use
        and also handle the overlap situations.

    Args:
        uow: The unit of work.
        panel_name (str): The name of the panel to create or update.
        science_reviewers (list): List of science reviewers.
        technical_reviewers (list): List of technical reviewers.
        proposal_list (list): List of proposal objects to assign to the panel.

    """
    assigned_at_utc = datetime.now(timezone.utc)

    # Load existing panel, if any
    existing_panels = get_latest_entity_by_id(
        uow.panels.query(CustomQuery(name=panel_name)), "panel_id"
    )
    panel: Panel | None = existing_panels[0] if existing_panels else None

    science = science_reviewers or []
    technical = technical_reviewers or []

    def _get_assignment_prsl_id(entry):
        return (
            entry["prsl_id"]
            if isinstance(entry, dict)
            else getattr(entry, "prsl_id", None)
        )

    if panel:
        # prsl_ids currently assigned to this panel
        existing_ids = {
            prsl_id
            for e in (panel.proposals or [])
            if (prsl_id := _get_assignment_prsl_id(e))
        }

        for incoming in proposals or []:
            prsl_id = getattr(incoming, "prsl_id", None)
            if not prsl_id:
                continue

            if prsl_id in existing_ids:
                # Already on panel → ensure UNDER_REVIEW
                existing_prsl: Proposal = uow.prsls.get(prsl_id)  # assumed to exist
                if existing_prsl.status != ProposalStatus.UNDER_REVIEW:
                    existing_prsl.status = ProposalStatus.UNDER_REVIEW
                    uow.prsls.add(existing_prsl)
                    logger.info(
                        "Proposal %s set to UNDER_REVIEW (already in panel '%s')",
                        prsl_id,
                        panel_name,
                    )
            else:
                # New to this panel → assign first, then set status & persist
                panel.proposals.append(
                    ProposalAssignment(prsl_id=prsl_id, assigned_on=assigned_at_utc)
                )
                # assumed to exist else willnot be in panel -risky in a way
                existing_prsl: Proposal = uow.prsls.get(prsl_id)
                if existing_prsl.status != ProposalStatus.UNDER_REVIEW:
                    existing_prsl.status = ProposalStatus.UNDER_REVIEW
                    uow.prsls.add(existing_prsl)
                    logger.info(
                        "Proposal %s set to UNDER_REVIEW and added to panel '%s'",
                        prsl_id,
                        panel_name,
                    )

        return uow.panels.add(panel)

    # No existing panel → create it; assign proposals, then set status for each
    # This part of the code may not be needed - discuss logic with SciOps
    assignments: list[ProposalAssignment] = []
    for incoming in proposals or []:
        prsl_id = getattr(incoming, "prsl_id", None)
        if not prsl_id:
            continue
        assignments.append(
            ProposalAssignment(prsl_id=prsl_id, assigned_on=assigned_at_utc)
        )

    new_panel = Panel(
        panel_id=generate_entity_id("panel"),
        name=panel_name,
        sci_reviewers=science,
        tech_reviewers=technical,
        proposals=assignments,
    )
    logger.info("Creating panel '%s' with %d proposal(s)", panel_name, len(assignments))
    return uow.panels.add(new_panel)


def _ref_prsl_id(ref: Any) -> str:
    """Extract prsl_id from either an object or a dict; raise if missing."""
    pid = ref["prsl_id"] if isinstance(ref, dict) else getattr(ref, "prsl_id", None)
    if not pid:
        raise BadRequestError("Missing prsl_id in submitted proposal reference.")
    return pid


def ensure_submitted_proposals_under_review(uow, submitted_refs: Iterable[Any]) -> None:
    """
    For each submitted proposal reference, load from ODA and set status
    to UNDER_REVIEW if not already.
    Persist each update.
    If a proposal doesn't exist, raise BadRequestError.

    Args:
        uow: Unit of work.
        submitted_refs: Iterable of objects/dicts each carrying a 'prsl_id' field.
    """
    for ref in submitted_refs:
        prsl_id = _ref_prsl_id(ref)
        try:
            proposal: Proposal = uow.prsls.get(prsl_id)
            if proposal.status != ProposalStatus.UNDER_REVIEW:
                proposal.status = ProposalStatus.UNDER_REVIEW
                uow.prsls.add(proposal)
                logger.info(
                    "Setting proposal %s status to UNDER REVIEW", proposal.prsl_id
                )
        except ODANotFound as exc:
            raise BadRequestError(f"Proposal '{prsl_id}' does not exist") from exc
