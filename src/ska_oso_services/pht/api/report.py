import logging
from typing import List

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.postgres import TABLES

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.service.report_processing import join_proposals_panels_reviews_decisions
from ska_oso_services.pht.utils.pht_helper import select_with_conditions

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
        proposals = uow.prsls.query(select_with_conditions(TABLES.proposals))
        panels = uow.panels.query(select_with_conditions(TABLES.panels))
        reviews = uow.rvws.query(select_with_conditions(TABLES.reviews))
        decisions = uow.pnlds.query(select_with_conditions(TABLES.panel_decisions))
    report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, decisions)
    return report
