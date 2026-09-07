import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Iterable

from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.pht.utils.constants import SV_NAME
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)


def transform_update_proposal(data: Proposal) -> Proposal:
    """
    Transforms and updates a given Proposal model.

    - If prsl_id is "new", sets it to "12345".
    - Sets submitted_on to now if submitted_by is provided.
    - Sets status based on presence of submitted_on.
    """

    # TODO : rethink the logic here - may need to move to UI
    if data.submitted_by:
        submitted_on = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "submitted"
    else:
        submitted_on = data.submitted_on
        status = "submitted" if submitted_on else "draft"

    return Proposal(
        prsl_id=data.prsl_id,
        cycle=data.cycle,
        submitted_by=data.submitted_by,
        submitted_on=submitted_on,
        status=status,
        proposal_info=data.proposal_info,
        observation_info=data.observation_info,
    )


def merge_latest_with_preference(
    *proposal_lists: Iterable["Proposal"],
) -> list["Proposal"]:
    """
    Combine proposal list and select a preference of "under review" to "submitted"
    """
    picked: OrderedDict[str, "Proposal"] = OrderedDict()
    for proposals in proposal_lists:
        for proposal in proposals or []:
            prsl_id = getattr(proposal, "prsl_id", None)
            if prsl_id and prsl_id not in picked:
                picked[prsl_id] = proposal
    return list(picked.values())


def get_panel_prsl_ids(uow, panel_name: str) -> set[str]:
    """
    Return the set of prsl_id values assigned to the *latest* panel
    matching `panel_name`. Empty set if not found.
    """
    refs = (
        get_latest_entity_by_id(
            uow.panels.query(CustomQuery(name=panel_name)),
            "panel_id",
        )
        or []
    )
    if not refs:
        return set()

    panel = uow.panels.get(refs[0].panel_id)
    if not panel:
        return set()

    return {p.prsl_id for p in (panel.proposals or []) if getattr(p, "prsl_id", None)}


def get_reviewer_prsl_ids(uow, reviewer_id: str, panel_name: str = SV_NAME) -> set[str]:
    """
    Return proposal IDs that are BOTH:
      • reviewed by `reviewer_id` (latest per review_id), AND
      • present on the given panel (latest by panel_id).
    """
    # Reviews → latest per review_id (avoid boolean coercion on query object)
    latest_reviews = (
        get_latest_entity_by_id(
            uow.rvws.query(CustomQuery(reviewer_id=reviewer_id)),
            "review_id",
        )
        or []
    )

    review_ids = {r.prsl_id for r in latest_reviews if getattr(r, "prsl_id", None)}
    if not review_ids:
        return set()

    panel_ids = get_panel_prsl_ids(uow, panel_name)
    if not panel_ids:
        return set()

    return review_ids & panel_ids
