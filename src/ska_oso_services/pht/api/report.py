import logging
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.postgres import TABLES
from sqlalchemy import select

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.service.report_processing import join_proposals_panels_reviews_decisions
from ska_oso_services.pht.service.security import Security, SecurityService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["PHT API - Report"])


def _report_not_wanted() -> None:
    # TODO: decide with stakeholders whether the report is needed, then remove it or this
    raise HTTPException(
        status_code=HTTPStatus.NOT_IMPLEMENTED, detail="The PHT report is not available."
    )


@router.get(
    "/",
    summary="Create a report for admin/coordinator",
    response_model=list[ProposalReportResponse],
    deprecated=True,
    # The first dependency runs first, so the route's own security and body are never reached
    dependencies=[
        Depends(_report_not_wanted),
        Security(
            roles={Role.INTERNAL},
            scopes={Scope.PHT_READ},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
)
def get_report() -> List[ProposalReportResponse]:
    """
    Creates a report for the PHT admin/coordinator.
    """

    logger.debug("GET REPORT create")
    logger.debug("GET REPORT")
    with oda.uow() as uow:
        proposals = uow.prsls.query(select(TABLES.proposals))
        panels = uow.panels.query(select(TABLES.panels))
        reviews = uow.rvws.query(select(TABLES.reviews))
        decisions = uow.pnlds.query(select(TABLES.panel_decisions))
    report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, decisions)
    return report
