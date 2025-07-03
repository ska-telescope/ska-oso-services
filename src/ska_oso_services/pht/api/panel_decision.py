import logging
from http import HTTPStatus

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm import PanelDecision

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/PanelDecision")


@router.post(
    "/create",
    summary="Create a new Panel decision",
)
def create_review(reviews: PanelDecision) -> str:
    """
    Creates a new decision for a panel in the ODA
    """

    LOGGER.debug("POST REVIEW create")

    try:
        with oda.uow() as uow:
            created_decision = uow.pnlds.add(reviews)
            uow.commit()
        return created_decision.decision_id
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err
