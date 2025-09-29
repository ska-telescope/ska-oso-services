import logging

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm import PanelDecision, Proposal
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel_decision import (
    PanelReviewStatus,
    Recommendation,
)

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.models.domain import PrslRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panel/decision", tags=["PMT API - Panel Decision"])


@router.post(
    "/create",
    summary="Create a new Panel decision for proposals",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READWRITE],
        )
    ],
)
def create_panel_decision(decisions: PanelDecision) -> str:
    """
    Create a new panel decision for proposals in a panel.

    Persists the panel decision in the underlying data store.

    Returns:
        str: The identifier (id) of the created panel decision.
    """

    logger.debug("POST PANEL DECISIONS create")

    try:
        with oda.uow() as uow:
            created_decision = uow.pnlds.add(decisions)
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
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
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
    logger.info("GET panel DECISION decision_id: %s", decision_id)

    with oda.uow() as uow:
        decision = uow.pnlds.get(decision_id)
    return decision


@router.get(
    "/users/{user_id}/decisions",
    summary="Get a list of Decisions created by the given user",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_panel_decisions_for_user(user_id: str) -> list[PanelDecision]:
    """
    Retrieves the panel Decision for the given user ID from the
    ODA, if available
    """

    logger.debug("GET Decision LIST query for the user: %s", user_id)

    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        decisions = uow.pnlds.query(query_param)
    return decisions


@router.put(
    "/{decision_id}",
    summary="Update an existing Decision",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READWRITE],
        )
    ],
)
def update_panel_decision(decision_id: str, decision: PanelDecision) -> PanelDecision:
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
        existing_decision = uow.pnlds.get(decision_id)

        if not existing_decision:
            logger.info("Decision not found for update: %s", decision_id)
            raise NotFoundError(detail="Decision not found: {decision_id}")

        try:
            updated_decision = uow.pnlds.add(decision)  # Add is used for update

            if updated_decision.status == PanelReviewStatus.DECIDED:

                existing_prsl: Proposal = uow.prsls.get(existing_decision.prsl_id)
                if not existing_prsl:
                    logger.info(
                        "Proposal not found for update: %s", existing_decision.prsl_id
                    )
                    raise NotFoundError(
                        detail="Proposal not found: {existing_decision.prsl_id}"
                    )

                match updated_decision.recommendation:
                    case None:
                        raise ValueError(
                            "recommendation cannot be None when decision status is DECIDED"
                        )  # moving the pdm?
                    case Recommendation.ACCEPTED:
                        existing_prsl.status = ProposalStatus.ACCEPTED
                    # case Recommendation.ACCEPTED_WITH_REVISION: # TODO: bump ODA to have latest pdm
                    #     existing_prsl.status = ProposalStatus.ACCEPTED
                    case Recommendation.REJECTED:
                        existing_prsl.status = ProposalStatus.REJECTED

                logger.info(
                    "Attempt to set Proposal %s to %s by Decision update '%s'",
                    existing_prsl.prsl_id,
                    existing_prsl.status,
                    existing_decision.decision_id,
                )
                uow.prsls.add(existing_prsl)

            uow.commit()
            logger.info("Decision %s updated successfully", decision_id)
            return updated_decision

        except ValueError as err:
            logger.error("Validation failed for Decision %s: %s", decision_id, err)
            raise BadRequestError(
                detail="Validation error while saving Decision: {err.args[0]}"
            ) from err
