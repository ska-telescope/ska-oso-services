import logging
from typing import Annotated

from fastapi import APIRouter, Response
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

router = APIRouter(tags=["PMT API - Panel Decision"])

_DEPRECATION_LINK = '</pht/panels/{pnl_id}/decisions>; rel="successor-version"'


# ---------------------------------------------------------------------------
# Shared business logic
# ---------------------------------------------------------------------------


def _apply_decision_status_to_proposal(uow, updated_decision: PanelDecision) -> None:
    """When a decision reaches DECIDED, propagate the recommendation to the proposal."""
    if updated_decision.status != PanelReviewStatus.DECIDED:
        return

    existing_prsl: Proposal = uow.prsls.get(updated_decision.prsl_id)
    if not existing_prsl:
        raise NotFoundError(detail=f"Proposal not found: {updated_decision.prsl_id}")

    match updated_decision.recommendation:
        case None:
            raise ValueError("recommendation cannot be None when decision is DECIDED")
        case Recommendation.ACCEPTED:
            existing_prsl.status = ProposalStatus.ACCEPTED
        case Recommendation.ACCEPTED_WITH_REVISION:
            existing_prsl.status = ProposalStatus.ACCEPTED_WITH_REVISION
        case Recommendation.REJECTED:
            existing_prsl.status = ProposalStatus.REJECTED

    logger.info(
        "Setting proposal %s to %s via decision %s",
        existing_prsl.prsl_id,
        existing_prsl.status,
        updated_decision.decision_id,
    )
    uow.prsls.add(existing_prsl)


# ---------------------------------------------------------------------------
# New namespaced routes  /panels/{pnl_id}/decisions/...
# ---------------------------------------------------------------------------


@router.get("/panels/{pnl_id}/decisions", summary="List all panel decisions for a panel")
def list_panel_decisions(
    pnl_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> list[PanelDecision]:
    security.panels.allowed_to_view_decision(pnl_id)
    with oda.uow() as uow:
        return (
            get_latest_entity_by_id(uow.pnlds.query(CustomQuery(panel_id=pnl_id)), "decision_id")
            or []
        )


@router.post("/panels/{pnl_id}/decisions", summary="Create a panel decision")
def create_panel_decision(
    pnl_id: str,
    decision: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
) -> str:
    security.panels.allowed_to_administer(pnl_id)
    try:
        with oda.uow() as uow:
            created = uow.pnlds.add(decision, security.auth.user_id)
            uow.commit()
        return created.decision_id
    except ValueError as err:
        raise BadRequestError(detail=f"Failed to create decision: '{err.args[0]}'") from err


@router.get(
    "/panels/{pnl_id}/decisions/{decision_id}",
    summary="Retrieve a panel decision",
)
def get_panel_decision(
    pnl_id: str,
    decision_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> PanelDecision:
    security.panels.allowed_to_view_decision(pnl_id)
    with oda.uow() as uow:
        decision = uow.pnlds.get(decision_id)
    if not decision:
        raise NotFoundError(detail=f"Decision not found: {decision_id}")
    return decision


@router.put(
    "/panels/{pnl_id}/decisions/{decision_id}",
    summary="Update a panel decision",
)
def update_panel_decision(
    pnl_id: str,
    decision_id: str,
    decision: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
) -> PanelDecision:
    if decision.decision_id != decision_id:
        raise UnprocessableEntityError(detail="Decision ID in path and body do not match.")
    security.panels.allowed_to_edit_decision(pnl_id)
    if decision.status == PanelReviewStatus.DECIDED:
        security.panels.allowed_to_submit_decision(pnl_id)
    with oda.uow() as uow:
        existing = uow.pnlds.get(decision_id)
        if not existing:
            raise NotFoundError(detail=f"Decision not found: {decision_id}")
        try:
            updated = uow.pnlds.add(decision, security.auth.user_id)
            _apply_decision_status_to_proposal(uow, updated)
            uow.commit()
        except ValueError as err:
            raise BadRequestError(
                detail=f"Validation error saving decision: {err.args[0]}"
            ) from err
    logger.info("Decision %s updated successfully", decision_id)
    return updated


# ---------------------------------------------------------------------------
# Deprecated routes  /panel/decision/...
# ---------------------------------------------------------------------------


@router.post(
    "/panel/decision/create",
    summary="Create a new Panel decision for proposals",
    deprecated=True,
)
def legacy_create_panel_decision(
    decisions: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
    response: Response,
) -> str:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    return create_panel_decision(pnl_id=decisions.panel_id, decision=decisions, security=security)


@router.get(
    "/panel/decision/{decision_id}",
    summary="Retrieve an existing panel decision for proposals",
    deprecated=True,
)
def legacy_get_panel_decision(
    decision_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
    response: Response,
) -> PanelDecision:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        existing = uow.pnlds.get(decision_id)
    if not existing:
        raise NotFoundError(detail=f"Decision not found: {decision_id}")
    return get_panel_decision(pnl_id=existing.panel_id, decision_id=decision_id, security=security)


@router.put(
    "/panel/decision/{decision_id}",
    summary="Update an existing Decision",
    deprecated=True,
)
def legacy_update_panel_decision(
    decision_id: str,
    decision: PanelDecision,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
    response: Response,
) -> PanelDecision:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        existing = uow.pnlds.get(decision_id)
    if not existing:
        raise NotFoundError(detail=f"Decision not found: {decision_id}")
    return update_panel_decision(
        pnl_id=existing.panel_id, decision_id=decision_id, decision=decision, security=security
    )


@router.get(
    "/panel/decision/",
    summary="Get a list of Decisions for all proposals",
    deprecated=True,
)
def legacy_get_panel_decisions_for_user(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
    response: Response,
) -> list[PanelDecision]:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        return get_latest_entity_by_id(uow.pnlds.query(CustomQuery()), "decision_id") or []
