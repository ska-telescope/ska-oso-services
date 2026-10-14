from functools import cache
from http import HTTPStatus
from typing import Any, Literal, NamedTuple
from urllib.parse import quote
from uuid import UUID, uuid7

import httpx
from fastapi import Header, HTTPException
from ska_ser_skuid import EntityType as et
from ska_ser_skuid import ShortSkuid

from ska_oso_services.common.client_credentials import (
    ClientCredentialsTokenProvider,
    TokenError,
)
from ska_oso_services.settings import get_settings

from .security.facts import get_group_name

# TODO: Replace with http.HTTPMethod once the runtime baseline is Python 3.11+.
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class ProposalGroupsTuple(NamedTuple):
    read: str
    write: str
    admin: str


class PanelGroupsTuple(NamedTuple):
    read: str
    admin: str


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


@cache
def get_token_provider() -> ClientCredentialsTokenProvider:
    """Process-wide token source for the User Portal, so every request shares one token."""
    portal = get_settings().userportal
    return ClientCredentialsTokenProvider(
        token_url=str(portal.token_url),
        client_id=portal.client_id,
        client_secret=portal.client_secret.get_secret_value(),
        scope=portal.token_scope,
        audience=portal.token_audience,
        timeout=portal.timeout,
    )


class UserPortalService:
    def __init__(self, x_request_id: str = Header(default_factory=lambda: str(uuid7()))) -> None:
        portal = get_settings().userportal
        self.base_url = str(portal.base_url).rstrip("/")
        self.timeout = portal.timeout
        self.tokens = get_token_provider()
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "ska-oso-services:pht",
            "X-Request-Id": x_request_id,
        }

    @staticmethod
    def _write_headers(acting_user: str, idempotent: bool = True) -> dict[str, str]:
        """Headers for state-changing calls: who we act on behalf of, and a per-call
        Idempotency-Key (required by the portal on POSTs)."""
        headers = {"X-Acting-User": acting_user}
        if idempotent:
            headers["Idempotency-Key"] = str(uuid7())
        return headers

    async def _call(
        self,
        method: HttpMethod,
        url: str,
        *,
        extra_headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        # Built once so a retry reuses the same Idempotency-Key
        headers = {**self.headers, **(extra_headers or {})}
        try:
            return await self._send(method, url, headers, params=params, json=json)
        except HTTPException as exc:
            if exc.status_code != HTTPStatus.UNAUTHORIZED:
                raise
        # Our token was rejected (revoked, or expired early), so get a new one and retry once
        self.tokens.invalidate()
        try:
            return await self._send(method, url, headers, params=params, json=json)
        except HTTPException as exc:
            if exc.status_code != HTTPStatus.UNAUTHORIZED:
                raise
            self.tokens.invalidate()
            # It's our credentials the portal rejected, not the end user's, so don't surface a 401
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                detail="User portal rejected our credentials",
            ) from exc

    async def _send(
        self,
        method: HttpMethod,
        url: str,
        headers: dict[str, str],
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        try:
            token = await self.tokens.get_token()
        except TokenError as err:
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                detail="Unable to authenticate to user portal",
            ) from err
        return await call_user_portal(
            method=method,
            url=url,
            params=params,
            json=json,
            headers={**headers, "Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )

    async def search_users(self, query: str, limit: int) -> dict[str, Any]:
        response = await self._call(
            method="GET",
            url=f"{self.base_url}/api/external/v1/users/search",
            params={"q": query, "limit": limit},
        )
        return response.json()

    async def _create_entity_groups(
        self,
        skuid: ShortSkuid,
        acting_user: str,
        read_desc: str,
        write_desc: str,
        admin_desc: str,
    ) -> tuple[str, str, str]:
        """Create the standard three-tier group set for an entity.

        Returns (read, write, admin) group names.
        """
        names = (
            get_group_name(skuid),
            get_group_name(skuid, write=True),
            get_group_name(skuid, admin=True),
        )
        for name, desc in zip(names, (read_desc, write_desc, admin_desc)):
            await self.create_group(name, acting_user, desc)
        return names

    async def create_proposal_groups(
        self, prsl_id: ShortSkuid[Literal[et.PRP]], acting_user: str
    ) -> ProposalGroupsTuple:
        read, write, admin = await self._create_entity_groups(
            prsl_id,
            acting_user,
            read_desc=f"Collaborators on proposal ({prsl_id})",
            write_desc=f"Co-Investigators with edit rights on proposal ({prsl_id})",
            admin_desc=f"Principal Investigator(s) for proposal ({prsl_id})",
        )
        return ProposalGroupsTuple(read=read, write=write, admin=admin)

    async def create_panel_groups(
        self, pnl_id: ShortSkuid[Literal[et.PNL]], acting_user: str
    ) -> PanelGroupsTuple:
        read, _, admin = await self._create_entity_groups(
            pnl_id,
            acting_user,
            read_desc=f"Members of panel ({pnl_id})",
            write_desc=f"UNUSED middle tier of panel membership ({pnl_id})",
            admin_desc=f"Chair(s) of panel ({pnl_id})",
        )
        return PanelGroupsTuple(read=read, admin=admin)

    async def create_group(
        self, group_name: str, acting_user: str, description: str = ""
    ) -> dict[str, Any]:
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups",
            json={"group_name": group_name, "display_name": description},
            extra_headers=self._write_headers(acting_user),
        )
        return response.json()

    async def create_membership(
        self,
        group_name: str,
        user_id: str,
        acting_user: str,
    ) -> dict[str, Any]:
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/members",
            json={"portal_user_id": user_id},
            extra_headers=self._write_headers(acting_user),
        )
        return response.json()

    async def create_invite(
        self,
        prsl_id: ShortSkuid[Literal[et.PRP]],
        invite_payload: dict[str, Any],
        acting_user: str,
    ) -> dict[str, Any]:
        group_name = get_group_name(prsl_id)
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/invites",
            json=invite_payload,
            extra_headers=self._write_headers(acting_user),
        )
        return response.json()

    async def get_invite(self, invite_id: UUID) -> dict[str, Any]:
        response = await self._call(
            method="GET",
            url=f"{self.base_url}/api/external/v1/invites/{invite_id}",
        )
        return response.json()

    async def list_invites(self, prsl_id: ShortSkuid[Literal[et.PRP]]) -> dict[str, Any]:
        response = await self._call(
            method="GET",
            url=f"{self.base_url}/api/external/v1/invites",
            params={"group_name": get_group_name(prsl_id)},
        )
        return response.json()

    async def delete_invite(self, invite_id: UUID, acting_user: str) -> dict[str, Any]:
        response = await self._call(
            method="DELETE",
            url=f"{self.base_url}/api/external/v1/invites/{invite_id}",
            extra_headers=self._write_headers(acting_user, idempotent=False),
        )
        return response.json()
