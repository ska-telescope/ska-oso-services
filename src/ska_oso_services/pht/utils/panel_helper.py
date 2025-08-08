import logging
import uuid
from datetime import datetime, timezone

from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.pht.model import PanelCreateResponse
from ska_oso_services.pht.utils.pht_handler import get_latest_entity_by_id

logger = logging.getLogger(__name__)


def generate_panel_id():
    #TODO: Remove this once the uuid generator by Brendan works!
    return f"panel-{uuid.uuid4().hex[:9]}"


def build_panel_response(panel_objs: dict) -> list[PanelCreateResponse]:
    """Builds a list of PanelCreateResponse objects from the given panel objects.
    Each response includes the panel_id, name, and proposal_count.
    """
    return [
        PanelCreateResponse(
            panel_id=panel.panel_id, name=name, proposal_count=len(panel.proposals)
        )
        for name, panel in panel_objs.items()
    ]


def build_sv_panel_proposals(proposals: list) -> list[dict]:
    """Builds the proposals list for a Science Verification panel."""
    return [
        {"prsl_id": proposal.prsl_id, "assigned_on": datetime.now(timezone.utc)}
        for proposal in proposals
    ]


def group_proposals_by_science_category(
    proposals: list, panel_names: list[str]
) -> dict[str, list]:
    """
    Groups proposals by science_category (inside proposal.info),
    only including those that match panel_names.
    Skips proposals with unmatched  science_category.
    """
    grouped = {name: [] for name in panel_names}
    skipped = 0
    for proposal in proposals:
        info = getattr(proposal, "info", None)
        science_category = (
            info.get("science_category")
            if isinstance(info, dict)
            else getattr(info, "science_category", None)
        )
        if science_category not in grouped:
            skipped += 1
            logger.warning(
                "Skipping proposal '%s' (science_category '%s' not in panel list)",
                proposal.prsl_id,
                science_category,
            )
            continue
        grouped[science_category].append(proposal)
    if skipped:
        logger.warning("%d proposals skipped due to missing science_category.", skipped)
    return grouped


def upsert_panel(uow, panel_name, reviewers, proposal_list):
    """
    Creates a new panel or updates an existing one with the given proposals.

    - If a panel with `panel_name` exists, appends any new proposals
    (by prsl_id) to it, avoiding duplicates.
    - If no panel exists, creates a new one with the given reviewers and proposals.

    Args:
        uow: The unit of work.
        panel_name (str): The name of the panel to create or update.
        reviewers (list): List of reviewers.
        proposal_list (list): List of proposal objects to assign to the panel.

    Returns:
        Panel: The created or updated Panel object.
    """
    now = datetime.now(timezone.utc)
    existing_panel = get_latest_entity_by_id(
        uow.panels.query(CustomQuery(name=panel_name)), "panel_id"
    )
    existing_panel = existing_panel[0] if existing_panel else None
    if existing_panel:
        existing_ids = {p["prsl_id"] for p in existing_panel.proposals}
        for proposal in proposal_list:
            if proposal.prsl_id not in existing_ids:
                existing_panel.proposals.append(
                    {"prsl_id": proposal.prsl_id, "assigned_on": now}
                )
        return existing_panel
    else:
        new_panel = Panel(
            panel_id=generate_panel_id(),
            name=panel_name,
            reviewers=reviewers,
            proposals=[
                {"prsl_id": proposal.prsl_id, "assigned_on": now}
                for proposal in proposal_list
            ],
        )
        return uow.panels.add(new_panel)
