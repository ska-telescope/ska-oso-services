import logging
from typing import List

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery

from ska_oso_services.common import oda
from ska_oso_services.pht.model import ProposalReport
from ska_oso_services.pht.utils.pht_handler import (
    get_latest_entity_by_id,
    join_proposals_panels_reviews_decisions,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["PHT API - Report"])


@router.get(
    "/{user_id}",
    summary="Create a report for admin/coordinator",
    response_model=List[ProposalReport],
)
def get_report(
    user_id: str,
) -> List[ProposalReport]:
    """
    Creates a new report for the PHT admin/coordinator.
    """

    LOGGER.debug("GET REPORT create")
    # TODO: get proposals using Andrey's new query so no need to pass user_id
    LOGGER.debug("GET REPORT")
    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        proposals = get_latest_entity_by_id(uow.prsls.query(query_param), "prsl_id")
        panels = get_latest_entity_by_id(
            uow.panels.query(query_param), "panel_id"  # pylint: disable=no-member
        )
        reviews = get_latest_entity_by_id(uow.rvws.query(query_param), "review_id")
        decisions = get_latest_entity_by_id(uow.pnlds.query(query_param), "prsl_id")
    report = join_proposals_panels_reviews_decisions(
        proposals, panels, reviews, decisions
    )
    return report
