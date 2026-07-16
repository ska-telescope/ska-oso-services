from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.models.invitations import (
    InvitationsListResponse,
    InviteCardResponse,
    InviteCreateListRequest,
    InviteDeleteResponse,
    UserSearchResponse,
)
from ska_oso_services.pht.service import user_portal

router = APIRouter(prefix="", tags=["PHT API - User Portal Invitations"])


READ_PERMISSIONS = Permissions(
    roles={Role.ANY},
    scopes={Scope.PHT_READ},
)
READWRITE_PERMISSIONS = Permissions(
    roles={Role.ANY},
    scopes={Scope.PHT_READWRITE},
)


def get_user_portal_service_read(
    auth: Annotated[AuthContext, READ_PERMISSIONS],
) -> user_portal.UserPortalService:
    return user_portal.UserPortalService(auth=auth)


def get_user_portal_service_readwrite(
    auth: Annotated[AuthContext, READWRITE_PERMISSIONS],
) -> user_portal.UserPortalService:
    return user_portal.UserPortalService(auth=auth)


@router.get(
    "/users/search",
    summary="Search users via external user portal",
    dependencies=[READ_PERMISSIONS],
    response_model=UserSearchResponse,
)
async def search_users(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_read)],
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(25, ge=1, le=100),
) -> UserSearchResponse:
    return UserSearchResponse.model_validate(await service.search_users(query=q, limit=limit))


@router.post(
    "/prsls/{prsl_id}/invites",
    summary="Create invites for proposal via external user portal",
    status_code=HTTPStatus.CREATED,
    dependencies=[READWRITE_PERMISSIONS],
    response_model=InvitationsListResponse,
)
async def create_invites(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_readwrite)],
    prsl_id: str,
    body: InviteCreateListRequest,
) -> InvitationsListResponse:
    invite_payloads: list[dict[str, object]] = []
    for invite in body.invites:
        invite_payload = invite.model_dump(mode="json", exclude_none=True)
        if "user_id" in invite_payload:
            invite_payload["portal_user_id"] = invite_payload.pop("user_id")
        invite_payloads.append(invite_payload)

    return InvitationsListResponse(
        invites=[
            InviteCardResponse.model_validate(item)
            for item in await service.create_invites(
                prsl_id=prsl_id,
                invite_payloads=invite_payloads,
            )
        ]
    )


@router.get(
    "/prsls/{prsl_id}/invites",
    summary="List invites for proposal via external user portal",
    dependencies=[READ_PERMISSIONS],
    response_model=InvitationsListResponse,
)
async def list_invites(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_read)],
    prsl_id: str,
) -> InvitationsListResponse:
    payload = await service.list_invites(prsl_id=prsl_id)
    return InvitationsListResponse(
        invites=[InviteCardResponse.model_validate(item) for item in payload.get("items", [])],
        next_cursor=payload.get("next_cursor"),
    )


@router.delete(
    "/prsls/{prsl_id}/invites/{invite_id}",
    summary="Delete invite for proposal via external user portal",
    dependencies=[READWRITE_PERMISSIONS],
    response_model=InviteDeleteResponse,
)
async def delete_invite(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_readwrite)],
    prsl_id: str,
    invite_id: UUID,
) -> InviteDeleteResponse:
    del prsl_id
    return InviteDeleteResponse.model_validate(await service.delete_invite(invite_id=invite_id))
