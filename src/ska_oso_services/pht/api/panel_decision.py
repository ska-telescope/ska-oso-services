import logging
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm import PanelDecision, Proposal
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel_decision import PanelReviewStatus, Recommendation

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panel/decision", tags=["PMT API - Panel Decision"])


# ---------------------------------------------------------------------------
# Active routes  /panel/decision
# ---------------------------------------------------------------------------


@router.post(
    "/create",
    summary="Create a new Panel decision for proposals",
)
def create_panel_decision(
    decisions: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
) -> str:
    security.panels.allowed_to_administer(decisions.panel_id)
    try:
        with oda.uow() as uow:
            created = uow.pnlds.add(decisions, security.auth.user_id)
            uow.commit()
        return created.decision_id
    except ValueError as err:
        raise BadRequestError(detail=f"Failed to create decision: '{err.args[0]}'") from err


@router.get(
    "/{decision_id}",
    summary="Retrieve an existing panel decision for proposals",
)
def get_panel_decision(
    decision_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> PanelDecision:
    with oda.uow() as uow:
        decision = uow.pnlds.get(decision_id)
    if not decision:
        raise NotFoundError(detail=f"Decision not found: {decision_id}")
    security.panels.allowed_to_view_decision(decision.panel_id)
    return decision


@router.put(
    "/{decision_id}",
    summary="Update an existing Decision",
)
def update_panel_decision(
    decision_id: str,
    decision: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
) -> PanelDecision:
    if decision.decision_id != decision_id:
        raise UnprocessableEntityError(detail="Decision ID in path and body do not match.")
    with oda.uow() as uow:
        existing = uow.pnlds.get(decision_id)
        if not existing:
            raise NotFoundError(detail=f"Decision not found: {decision_id}")
        security.panels.allowed_to_edit_decision(existing.panel_id)
        if decision.status == PanelReviewStatus.DECIDED:
            security.panels.allowed_to_submit_decision(existing.panel_id)
        try:
            updated = uow.pnlds.add(decision, security.auth.user_id)

            if updated.status == PanelReviewStatus.DECIDED:
                existing_prsl: Proposal = uow.prsls.get(existing.prsl_id)
                if not existing_prsl:
                    raise NotFoundError(detail=f"Proposal not found: {existing.prsl_id}")

                match updated.recommendation:
                    case None:
                        raise ValueError("recommendation cannot be None when decision is DECIDED")
                    case Recommendation.ACCEPTED:
                        existing_prsl.status = ProposalStatus.ACCEPTED
                    case Recommendation.ACCEPTED_WITH_REVISION:
                        existing_prsl.status = ProposalStatus.ACCEPTED_WITH_REVISION
                    case Recommendation.REJECTED:
                        existing_prsl.status = ProposalStatus.REJECTED

                logger.info(
                    "Attempt to set Proposal %s to %s by Decision update '%s'",
                    existing_prsl.prsl_id,
                    existing_prsl.status,
                    existing.decision_id,
                )
                uow.prsls.add(existing_prsl)

            uow.commit()
        except ValueError as err:
            raise BadRequestError(
                detail=f"Validation error saving decision: {err.args[0]}"
            ) from err
    logger.info("Decision %s updated successfully", decision_id)
    return updated


@router.get(
    "/",
    summary="Get a list of Decisions for all proposals",
)
def get_panel_decisions_for_user(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
) -> list[PanelDecision]:
    with oda.uow() as uow:
        return get_latest_entity_by_id(uow.pnlds.query(CustomQuery()), "decision_id") or []
