import logging
from typing import List

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.repository.domain import CustomQuery

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.service.report_processing import join_proposals_panels_reviews_decisions
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["PHT API - Report"])


@router.get(
    "/",
    summary="Create a report for admin/coordinator",
    response_model=list[ProposalReportResponse],
    dependencies=[
        Permissions(roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ])
    ],
)
def get_report() -> List[ProposalReportResponse]:
    """
    Creates a report for the PHT admin/coordinator.
    """

    logger.debug("GET REPORT create")
    logger.debug("GET REPORT")
    with oda.uow() as uow:
        proposal_query_param = CustomQuery()
        query_param = CustomQuery()
        proposals = get_latest_entity_by_id(uow.prsls.query(proposal_query_param), "prsl_id")
        panels = get_latest_entity_by_id(
            uow.panels.query(query_param), "panel_id"  # pylint: disable=no-member
        )
        reviews = get_latest_entity_by_id(uow.rvws.query(query_param), "review_id")
        decisions = get_latest_entity_by_id(uow.pnlds.query(query_param), "decision_id")
    report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, decisions)
    return report
