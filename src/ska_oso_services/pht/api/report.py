import logging
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.repository.domain import CustomQuery

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.service.report_processing import join_proposals_panels_reviews_decisions
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

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
        proposal_query_param = CustomQuery()
        query_param = CustomQuery()
        proposals = get_latest_entity_by_id(uow.prsls.query(proposal_query_param), "prsl_id")
        panels = get_latest_entity_by_id(
            uow.panels.query(query_param),
            "panel_id",  # pylint: disable=no-member
        )
        reviews = get_latest_entity_by_id(uow.rvws.query(query_param), "review_id")
        decisions = get_latest_entity_by_id(uow.pnlds.query(query_param), "decision_id")
    report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, decisions)
    return report
