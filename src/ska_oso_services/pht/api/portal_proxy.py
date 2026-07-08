from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, model_validator
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from typing_extensions import Self

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.service import user_portal

router = APIRouter(prefix="", tags=["PHT API - User Portal Proxy"])


class InviteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    email: str | None = None

    @model_validator(mode="after")
    def xor_invite_type(self) -> Self:
        has_user_id = self.user_id is not None
        has_email = self.email is not None
        if has_user_id == has_email:
            raise ValueError("Exactly one of user_id or email must be provided")
        return self


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
)
async def search_users(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_read)],
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(25, ge=1, le=100),
) -> dict:
    return await service.search_users(query=q, limit=limit)


@router.post(
    "/proposals/{prsl_id}/invites",
    summary="Create invite for proposal via external user portal",
    status_code=HTTPStatus.CREATED,
    dependencies=[READWRITE_PERMISSIONS],
)
async def create_invite(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_readwrite)],
    prsl_id: str,
    body: InviteCreateRequest,
) -> dict:
    invite_payload = body.model_dump(mode="json", exclude_none=True)
    if "user_id" in invite_payload:
        invite_payload["portal_user_id"] = invite_payload.pop("user_id")

    return await service.create_invite(
        prsl_id=prsl_id,
        invite_payload=invite_payload,
    )


@router.get(
    "/proposals/{prsl_id}/invites",
    summary="List invites for proposal via external user portal",
    dependencies=[READ_PERMISSIONS],
)
async def list_invites(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_read)],
    prsl_id: str,
) -> dict:
    return await service.list_invites(prsl_id=prsl_id)


@router.delete(
    "/proposals/{prsl_id}/invites/{invite_id}",
    summary="Delete invite for proposal via external user portal",
    dependencies=[READWRITE_PERMISSIONS],
)
async def delete_invite(
    service: Annotated[user_portal.UserPortalService, Depends(get_user_portal_service_readwrite)],
    prsl_id: str,
    invite_id: UUID,
) -> dict:
    del prsl_id
    return await service.delete_invite(invite_id=invite_id)
