from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from ska_aaa_authhelpers import Role
from ska_ser_skuid import EntityType, ShortSkuid

from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.models.invitations import (
    InvitationsListResponse,
    InviteCardResponse,
    InviteCreateListRequest,
    InviteDeleteResponse,
    UserSearchResponse,
)
from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.security import Security, SecurityService

ProposalID = ShortSkuid[Literal[EntityType.PRP]]

router = APIRouter(prefix="", tags=["PHT API - User Portal Invitations"])


@router.get(
    "/users/search",
    summary="Search users via external user portal",
    dependencies=[Security(roles={Role.ANY}, scopes={Scope.PHT_READ})],
    response_model=UserSearchResponse,
)
async def search_users(
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(25, ge=1, le=100),
) -> UserSearchResponse:
    return UserSearchResponse.model_validate(await service.search_users(query=q, limit=limit))


@router.post(
    "/prsls/{prsl_id}/invites",
    summary="Create invites for proposal via external user portal",
    status_code=HTTPStatus.CREATED,
    response_model=InvitationsListResponse,
)
async def create_invites(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
    body: InviteCreateListRequest,
) -> InvitationsListResponse:
    security.proposals.allowed_to_administer(prsl_id)

    created_invites: list[InviteCardResponse] = []
    for invite in body.invites:
        invite_payload = invite.model_dump(mode="json", by_alias=True, exclude_none=True)
        created_invites.append(
            InviteCardResponse.model_validate(
                await service.create_invite(
                    prsl_id=prsl_id,
                    invite_payload=invite_payload,
                )
            )
        )

    return InvitationsListResponse(invites=created_invites)


@router.get(
    "/prsls/{prsl_id}/invites",
    summary="List invites for proposal via external user portal",
    response_model=InvitationsListResponse,
)
async def list_invites(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
) -> InvitationsListResponse:
    security.proposals.allowed_to_view_other_members(prsl_id)
    members_payload = await service.list_invites(prsl_id=prsl_id)

    invited = [
        InviteCardResponse.model_validate(item)
        for item in members_payload.get("items", [])
        if item.get("claim_state") != "accepted"
    ]

    return InvitationsListResponse(invites=invited)


@router.delete(
    "/prsls/{prsl_id}/invites/{invite_id}",
    summary="Delete invite for proposal via external user portal",
    response_model=InviteDeleteResponse,
)
async def delete_invite(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
    invite_id: UUID,
) -> InviteDeleteResponse:
    security.proposals.allowed_to_administer(prsl_id)

    return InviteDeleteResponse.model_validate(await service.delete_invite(invite_id=invite_id))


@router.get(
    "/prsls/{prsl_id}/members",
    summary="List members of the proposal",
    response_model=InvitationsListResponse,
)
async def list_members(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
) -> InvitationsListResponse:
    security.proposals.allowed_to_view_other_members(prsl_id)
    members_payload = await service.list_invites(prsl_id=prsl_id)

    members = [
        InviteCardResponse.model_validate(item)
        for item in members_payload.get("items", [])
        if item.get("claim_state") == "accepted"
    ]
    return InvitationsListResponse(invites=members)
