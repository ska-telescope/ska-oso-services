import logging
from typing import List

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery

from ska_oso_services.common import oda
from ska_oso_services.pht.model import ProposalReport
from ska_oso_services.pht.utils.pht_handler import (
    join_proposals_panels_reviews_decisions,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/report")


def get_latest_by_id(entities, id_attr: str) -> list:
    latest = {}
    for entity in entities:
        key = getattr(entity, id_attr)
        version = entity.metadata.version
        if key not in latest or version > latest[key].metadata.version:
            latest[key] = entity
    return list(latest.values())


@router.get(
    "/{user_id}",
    summary="Create a report for admin",
)
def get_report(
    user_id: str,
) -> List[ProposalReport]:
    """
    Creates a new report for the PHT admin
    """

    LOGGER.debug("GET REPORT create")
    # TODO: get proposals using Andrey's new query -- need to add an endpoint for this
    # get the latest version for all these entities
    LOGGER.debug("GET REPORT")
    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        proposals = get_latest_by_id(uow.prsls.query(query_param), "prsl_id")
        panels = get_latest_by_id(
            uow.panels.query(query_param), "panel_id"  # pylint: disable=no-member
        )  # pylint: disable=no-member
        reviews = get_latest_by_id(uow.rvws.query(query_param), "review_id")
        decisions = get_latest_by_id(uow.pnlds.query(query_param), "prsl_id")
    report = join_proposals_panels_reviews_decisions(
        proposals, panels, reviews, decisions
    )
    return report
