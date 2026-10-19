import asyncio
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from ska_aaa_authhelpers import Role
from ska_ser_skuid import EntityType, ShortSkuid

from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import NotFoundError
from ska_oso_services.pht.models.invitations import (
    InvitationsListResponse,
    InviteBulkCreateResult,
    InviteCardResponse,
    InviteCreateListRequest,
    InviteCreateListResponse,
    InviteDeleteResponse,
    InviteFailure,
    ProposalMember,
    ProposalMembersResponse,
    UserSearchResponse,
)
from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.service.security.facts import get_group_name, get_group_skuid

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
    return user_portal.parse_portal_response(
        UserSearchResponse, await service.search_users(query=q, limit=limit)
    )


@router.post(
    "/prsls/{prsl_id}/invites",
    summary="Create invites for proposal via external user portal",
    response_model=InviteCreateListResponse,
)
async def create_invites(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
    body: InviteCreateListRequest,
) -> InviteCreateListResponse:
    """
    Invites each address independently: one that fails (already invited, say) is
    listed under "failed" and doesn't stop the others.
    """
    security.proposals.allowed_to_administer(prsl_id)

    bulk = user_portal.parse_portal_response(
        InviteBulkCreateResult,
        await service.create_invites(
            prsl_id=prsl_id,
            invite_payloads=[
                invite.model_dump(mode="json", by_alias=True, exclude_none=True)
                for invite in body.invites
            ],
            acting_as=security.auth,
        ),
    )

    created, failed = [], []
    for result in bulk.results:
        if result.invite is not None:
            created.append(result.invite)
        else:
            failed.append(
                InviteFailure(email=result.email, status=result.status, detail=result.detail)
            )
    return InviteCreateListResponse(invites=created, failed=failed)


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
    invited = [
        user_portal.parse_portal_response(InviteCardResponse, item)
        for item in await service.list_invites(prsl_id=prsl_id)
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
    invite = user_portal.parse_portal_response(
        InviteCardResponse, await service.get_invite(invite_id)
    )
    if get_group_skuid(invite.group_name) != prsl_id:
        # invite_id does not belong to prsl_id, so this path does not resolve to a resource
        raise NotFoundError(detail=f"Invite {invite_id} not found for proposal {prsl_id}")

    security.proposals.allowed_to_administer(prsl_id)

    return user_portal.parse_portal_response(
        InviteDeleteResponse,
        await service.delete_invite(invite_id=invite_id, acting_as=security.auth),
    )


@router.get(
    "/prsls/{prsl_id}/members",
    summary="List members of the proposal's groups",
    dependencies=[Security(roles={Role.ANY}, scopes={Scope.PHT_READ})],
    response_model=ProposalMembersResponse,
)
async def list_members(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ}),
    ],
    service: Annotated[user_portal.UserPortalService, Depends(user_portal.UserPortalService)],
    prsl_id: ProposalID,
) -> ProposalMembersResponse:
    security.proposals.allowed_to_view_other_members(prsl_id)

    # (group, has_write, is_admin) for each tier of the proposal's groups
    tiers = [
        (get_group_name(prsl_id), False, False),
        (get_group_name(prsl_id, write=True), True, False),
        (get_group_name(prsl_id, admin=True), True, True),
    ]
    payloads = await asyncio.gather(
        *(service.list_group_members(group_name) for group_name, _, _ in tiers)
    )

    # Someone can be in several tiers (or only a higher one, like the PI who
    # created the proposal), so merge per person and keep their highest access
    members: dict[str, ProposalMember] = {}
    for (_, has_write, is_admin), payload in zip(tiers, payloads):
        for item in payload["members"]:
            member = user_portal.parse_portal_response(ProposalMember, item)
            member = members.get(member.user_id, member)
            members[member.user_id] = member.model_copy(
                update={
                    "has_write": member.has_write or has_write,
                    "is_admin": member.is_admin or is_admin,
                }
            )

    return ProposalMembersResponse(
        members=sorted(
            members.values(),
            key=lambda m: (not m.is_admin, not m.has_write, m.display_name or ""),
        ),
        stale=any(payload["stale"] for payload in payloads),
    )
