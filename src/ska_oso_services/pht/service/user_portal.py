from http import HTTPStatus
from typing import Any, Literal, NamedTuple
from uuid import UUID, uuid1

import httpx
from fastapi import Header, HTTPException
from ska_ser_skuid import EntityType as et
from ska_ser_skuid import ShortSkuid

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


class UserPortalService:
    def __init__(self, x_request_id: str = Header(default_factory=lambda: str(uuid1()))) -> None:
        portal = get_settings().userportal
        self.base_url = str(portal.base_url).rstrip("/")
        self.timeout = portal.timeout
        self.headers = {
            "Authorization": portal.api_key,
            "Accept": "application/json",
            "User-Agent": "ska-oso-services:pht",
            "X-Request-Id": x_request_id,
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

    async def _create_entity_groups(
        self,
        skuid: ShortSkuid,
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
            await self.create_group(name, desc)
        return names

    async def create_proposal_groups(
        self, prsl_id: ShortSkuid[Literal[et.PRP]]
    ) -> ProposalGroupsTuple:
        read, write, admin = await self._create_entity_groups(
            prsl_id,
            read_desc=f"Collaborators on proposal ({prsl_id})",
            write_desc=f"Co-Investigators with edit rights on proposal ({prsl_id})",
            admin_desc=f"Principal Investigator(s) for proposal ({prsl_id})",
        )
        return ProposalGroupsTuple(read=read, write=write, admin=admin)

    async def create_panel_groups(self, pnl_id: ShortSkuid[Literal[et.PNL]]) -> PanelGroupsTuple:
        read, _, admin = await self._create_entity_groups(
            pnl_id,
            read_desc=f"Members of panel ({pnl_id})",
            write_desc=f"Panel members with additional privileges ({pnl_id})",
            admin_desc=f"Chair(s) of panel ({pnl_id})",
        )
        return PanelGroupsTuple(read=read, admin=admin)

    async def create_group(self, group_name: str, description: str = "") -> dict[str, Any]:
        response = await call_user_portal(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups",
            json={"name": group_name, "description": description},
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def create_membership(
        self,
        group_name: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        response = await call_user_portal(
            method="PUT",
            url=(f"{self.base_url}/api/external/v1/groups/{group_name}/members/{user_id}"),
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def create_invite(
        self, prsl_id: ShortSkuid[Literal[et.PRP]], invite_payload: dict[str, Any]
    ) -> dict[str, Any]:
        group_name = get_group_name(prsl_id)
        response = await call_user_portal(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{group_name}/invites",
            json=invite_payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        return response.json()

    async def list_invites(self, prsl_id: ShortSkuid[Literal[et.PRP]]) -> dict[str, Any]:
        response = await call_user_portal(
            method="GET",
            url=f"{self.base_url}/api/external/v1/invites",
            params={"group_name": get_group_name(prsl_id)},
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
