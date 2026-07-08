from http import HTTPStatus
from os import getenv
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException
from ska_aaa_authhelpers.auth_context import AuthContext

DEFAULT_TIMEOUT_SECONDS = 10
USER_PORTAL_BASE_URL = getenv("USER_PORTAL_BASE_URL", "").rstrip("/")
assert USER_PORTAL_BASE_URL


def group_name_for_proposal(prsl_id: str) -> str:
    return f"app:pht:{prsl_id}"


def build_headers(auth: AuthContext) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {auth.access_token}",
        "Accept": "application/json",
        "User-Agent": "ska-oso-services:pht",
        "X-Trace-Id": auth.trace,
    }


async def call_user_portal(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
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


def filter_user_search_results(results: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    lowered_query = query.lower()
    return [
        item
        for item in results
        if lowered_query in str(item.get("display_name", "")).lower()
        or lowered_query in str(item.get("email", "")).lower()
    ]


async def search_users(query: str, limit: int, headers: dict[str, str]) -> dict[str, Any]:
    response = await call_user_portal(
        method="GET",
        url=f"{USER_PORTAL_BASE_URL}/api/external/v1/users/search",
        params={"q": query, "limit": limit},
        headers=headers,
    )

    payload = response.json()
    results = payload.get("results") or []
    return {"results": filter_user_search_results(results, query)}


async def create_invite(
    prsl_id: str,
    invite_payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    group_name = group_name_for_proposal(prsl_id)
    response = await call_user_portal(
        method="POST",
        url=f"{USER_PORTAL_BASE_URL}/api/external/v1/groups/{group_name}/invites",
        json=invite_payload,
        headers=headers,
    )

    payload = response.json()
    if isinstance(payload, dict):
        payload["group_name"] = group_name
    return payload


async def list_invites(prsl_id: str, headers: dict[str, str]) -> dict[str, Any]:
    response = await call_user_portal(
        method="GET",
        url=f"{USER_PORTAL_BASE_URL}/api/external/v1/invites",
        params={"group_name": group_name_for_proposal(prsl_id)},
        headers=headers,
    )
    return response.json()


async def delete_invite(invite_id: UUID, headers: dict[str, str]) -> dict[str, Any]:
    response = await call_user_portal(
        method="DELETE",
        url=f"{USER_PORTAL_BASE_URL}/api/external/v1/invites/{invite_id}",
        headers=headers,
    )
    return response.json()


class UserPortalService:
    def __init__(self, auth: AuthContext) -> None:
        self.headers = build_headers(auth)

    async def search_users(self, query: str, limit: int) -> dict[str, Any]:
        return await search_users(query=query, limit=limit, headers=self.headers)

    async def create_invite(self, prsl_id: str, invite_payload: dict[str, Any]) -> dict[str, Any]:
        return await create_invite(
            prsl_id=prsl_id,
            invite_payload=invite_payload,
            headers=self.headers,
        )

    async def list_invites(self, prsl_id: str) -> dict[str, Any]:
        return await list_invites(prsl_id=prsl_id, headers=self.headers)

    async def delete_invite(self, invite_id: UUID) -> dict[str, Any]:
        return await delete_invite(invite_id=invite_id, headers=self.headers)
