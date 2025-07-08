import logging

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm import PanelDecision

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/panel-decisions")


@router.post(
    "/",
    summary="Create a new Panel decision",
)
def create_panel_decision(decisions: PanelDecision) -> str:
    """
    Creates a new decision for a panel in the ODA
    """

    LOGGER.debug("POST DECISIONS create")

    try:
        with oda.uow() as uow:
            created_decision = uow.pnlds.add(decisions)
            uow.commit()
        return created_decision.decision_id
    except ValueError as err:
        LOGGER.exception(
            "ValueError when adding Decision for a panel to the ODA: %s", err
        )
        raise BadRequestError(
            detail=f"Failed when attempting to create a Decision: '{err.args[0]}'",
        ) from err


@router.get("/{decision_id}", summary="Retrieve an existing decision")
def get_panel_decision(decision_id: str) -> PanelDecision:
    """Retrieves a decision for a panel from the ODA based on the decision_id."""
    LOGGER.debug("GET panel DECISION decision_id: %s", decision_id)

    with oda.uow() as uow:
        decision = uow.pnlds.get(decision_id)
    return decision


@router.get("/list/{user_id}", summary="Get a list of Decisions created by a user")
def get_panel_decisions_for_user(user_id: str) -> list[PanelDecision]:
    """
    Retrieves the panel Decision for the given user ID from the
    ODA, if available
    """

    LOGGER.debug("GET Decision LIST query for the user: %s", user_id)

    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        decisions = uow.pnlds.query(query_param)
    return decisions


@router.put("/{decision_id}", summary="Update an existing Decision")
def update_panel_decision(decision_id: str, decision: PanelDecision) -> PanelDecision:
    """
    Updates a decision in the ODA.
    """
    LOGGER.debug("PUT Decision - Attempting update for Decision_id: %s", decision_id)

    # Ensure ID match
    if decision.decision_id != decision_id:
        LOGGER.warning(
            "Decision ID mismatch: decision ID=%s in path, body ID=%s",
            decision_id,
            decision.decision_id,
        )
        raise UnprocessableEntityError(
            detail="Decision ID in path and body do not match."
        )

    with oda.uow() as uow:
        # Verify Decision exists
        existing = uow.pnlds.get(decision_id)
        if not existing:
            LOGGER.info("Decision not found for update: %s", decision_id)
            raise NotFoundError(detail="Decision not found: {decision_id}")

        try:
            updated_decision = uow.pnlds.add(decision)  # Add is used for update
            uow.commit()
            LOGGER.info("Decision %s updated successfully", decision_id)
            return updated_decision

        except ValueError as err:
            LOGGER.error("Validation failed for Decision %s: %s", decision_id, err)
            raise BadRequestError(
                detail="Validation error while saving Decision: {err.args[0]}"
            ) from err
