from http import HTTPStatus
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import HTTPException
from ska_aaa_authhelpers.auth_context import AuthContext

from ska_oso_services.settings import get_settings

# TODO: Replace with http.HTTPMethod once the runtime baseline is Python 3.11+.
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def group_name_for_proposal(prsl_id: str) -> str:
    return f"app:pht:{prsl_id}"


async def call_user_portal(
    method: HttpMethod,
    url: str,
    timeout: int,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
            )

        if response.status_code < 400:
            return response

        detail = response.text or response.reason_phrase
        if response.status_code >= 500:
            raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail=detail)

        raise HTTPException(status_code=response.status_code, detail=detail)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=f"Failed to contact user portal: {exc}",
        ) from exc


class UserPortalService:
    def __init__(self, auth: AuthContext) -> None:
        portal = get_settings().userportal
        self.base_url = portal.base_url
        self.timeout = portal.timeout
        self.headers = {
            "Authorization": portal.api_key,
            "Accept": "application/json",
            "User-Agent": "ska-oso-services:pht",
            "X-Request-Id": auth.trace,
        }

    async def search_users(self, query: str, limit: int) -> dict[str, Any]:
        response = await call_user_portal(
            method="GET",
            url=f"{self.base_url}/api/external/v1/users/search",
            params={"q": query, "limit": limit},
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def create_invite(self, prsl_id: str, invite_payload: dict[str, Any]) -> dict[str, Any]:
        group_name = group_name_for_proposal(prsl_id)
        response = await call_user_portal(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{group_name}/invites",
            json=invite_payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def list_invites(self, prsl_id: str) -> dict[str, Any]:
        response = await call_user_portal(
            method="GET",
            url=f"{self.base_url}/api/external/v1/invites",
            params={"group_name": group_name_for_proposal(prsl_id)},
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def delete_invite(self, invite_id: UUID) -> dict[str, Any]:
        response = await call_user_portal(
            method="DELETE",
            url=f"{self.base_url}/api/external/v1/invites/{invite_id}",
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()
