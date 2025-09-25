import logging
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm import PanelDecision

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.models.domain import PrslRole
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panel/decision", tags=["PMT API - Panel Decision"])


@router.post(
    "/create",
    summary="Create a new Panel decision for proposals",
)
def create_panel_decision(
    decisions: PanelDecision,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> str:
    """
    Create a new panel decision for proposals in a panel.

    Persists the panel decision in the underlying data store.

    Returns:
        str: The identifier (id) of the created panel decision.
    """

    logger.debug("POST PANEL DECISIONS create")

    try:
        with oda.uow() as uow:
            created_decision = uow.pnlds.add(decisions, auth.user_id)
            uow.commit()
        return created_decision.decision_id
    except ValueError as err:
        logger.exception(
            "ValueError when adding Decision for a panel to the ODA: %s", err
        )
        raise BadRequestError(
            detail=f"Failed when attempting to create a Decision: '{err.args[0]}'",
        ) from err


@router.get(
    "/{decision_id}",
    summary="Retrieve an existing panel decision for proposals",
    dependencies=[
        Permissions(
            roles=[
                PrslRole.OPS_PROPOSAL_ADMIN,
                PrslRole.OPS_REVIEW_CHAIR,
                Role.SW_ENGINEER,
            ],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_panel_decision(decision_id: str) -> PanelDecision:
    """
    Retrieves a decision for a panel from the ODA based on the decision_id.

    Returns:
        PanelDecision: The created panel decision, validated against the schema.
        This includes the metadata such as `created_by`, and `created_on`.
    """
    logger.debug("GET panel DECISION decision_id: %s", decision_id)

    with oda.uow() as uow:
        decision = uow.pnlds.get(decision_id)
    return decision


@router.put(
    "/{decision_id}",
    summary="Update an existing Decision",
)
def update_panel_decision(
    decision_id: str,
    decision: PanelDecision,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, PrslRole.OPS_REVIEW_CHAIR},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> PanelDecision:
    """
    Updates a decision in the ODA.
    """

    logger.debug("PUT Decision - Attempting update for Decision_id: %s", decision_id)

    # Ensure ID match
    if decision.decision_id != decision_id:
        logger.warning(
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
            logger.info("Decision not found for update: %s", decision_id)
            raise NotFoundError(detail="Decision not found: {decision_id}")

        try:
            updated_decision = uow.pnlds.add(decision, auth.user_id)
            uow.commit()
            logger.info("Decision %s updated successfully", decision_id)
            return updated_decision

        except ValueError as err:
            logger.error("Validation failed for Decision %s: %s", decision_id, err)
            raise BadRequestError(
                detail="Validation error while saving Decision: {err.args[0]}"
            ) from err


@router.get(
    "/",
    summary="Get a list of Decisions for all proposals",
    dependencies=[
        Permissions(
            roles=[
                PrslRole.OPS_PROPOSAL_ADMIN,
                Role.SW_ENGINEER,
                PrslRole.OPS_REVIEW_CHAIR,
            ],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_panel_decisions_for_user() -> list[PanelDecision]:
    """
    Retrieves the latest panel Decision for all proposals from the
    ODA, if available
    """

    logger.debug("GET Decision LIST query for the user")

    with oda.uow() as uow:
        decisions = get_latest_entity_by_id(
            uow.pnlds.query(CustomQuery()), "decision_id"
        )
    return decisions
