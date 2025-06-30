import datetime
import logging

from fastapi import APIRouter
from ska_db_oda.persistence.domain.errors import ODANotFound
from ska_db_oda.rest.api import get_qry_params
from ska_db_oda.rest.model import ApiQueryParameters
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.utils.constants import REVIEWERS
from ska_oso_services.pht.utils.validation import validate_duplicates

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/panels", summary="Create a panel")
def create_panel(param: Panel) -> str:
    logger.debug("POST panel")

    with oda.uow() as uow:
        reviewer_ids = validate_duplicates(param.reviewers, "reviewer_id")
        for reviewer_id in reviewer_ids:
            if not any([r["id"] == reviewer_id for r in REVIEWERS]):
                raise BadRequestError(f"Reviewer '{reviewer_id}' does not exist")

        proposal_ids = validate_duplicates(param.proposals, "prsl_id")
        for proposal_id in proposal_ids:
            try:
                uow.prsls.get(proposal_id)
            except ODANotFound:
                raise BadRequestError(f"Proposal '{proposal_id}' does not exist")

        panel: Panel = uow.panels.add(param)  # pylint: disable=no-member
        uow.commit()
    logger.info("Panel successfully created with ID %s", panel.panel_id)
    return panel.panel_id


@router.get("/panels/{panel_id}", summary="Retrieve an existing panel")
def get_panel(panel_id: str) -> Panel:
    logger.debug("GET panel: %s", panel_id)

    with oda.uow() as uow:
        panel = uow.panels.get(panel_id)  # pylint: disable=no-member
    logger.info("Proposal retrieved successfully: %s", panel_id)
    return panel


@router.get("/panels", summary="Get all panels")
def get_panels() -> list[Panel]:
    logger.debug("GET all panels")

    query_params = ApiQueryParameters(
        created_after=datetime.datetime(2025, 1, 1, 0, 0),
    )
    query_param = get_qry_params(query_params)

    with oda.uow() as uow:
        panels = uow.panels.query(query_param)  # pylint: disable=no-member
    return panels
