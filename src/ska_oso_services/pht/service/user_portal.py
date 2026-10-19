import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import cache
from http import HTTPStatus
from typing import Any, Literal, NamedTuple
from urllib.parse import quote
from uuid import UUID, uuid7

import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from ska_aaa_authhelpers import AuthContext
from ska_ser_skuid import EntityType as et
from ska_ser_skuid import ShortSkuid

from ska_oso_services.common.client_credentials import (
    ClientCredentialsTokenProvider,
    TokenError,
)
from ska_oso_services.common.error_handling import DuplicateError, NotFoundError
from ska_oso_services.settings import get_settings

from .security.facts import get_group_name

LOGGER = logging.getLogger(__name__)

# The portal's default page of its invites feed
INVITE_PAGE_SIZE = 500

# TODO: Replace with http.HTTPMethod once the runtime baseline is Python 3.11+.
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class UserPortalError(HTTPException):
    """
    The User Portal failed us, rather than the caller asking for something it
    can't have, so these are all 502s. (A portal 404 or 409 is about the caller's
    request and becomes our own NotFoundError or DuplicateError instead.)
    """

    code = HTTPStatus.BAD_GATEWAY

    def __init__(self, detail: str, upstream_status: int | None = None) -> None:
        self.upstream_status = upstream_status
        # Callers only see a 502, so make sure whoever is on call can see why
        LOGGER.error("%s: %s (upstream status %s)", type(self).__name__, detail, upstream_status)
        super().__init__(status_code=self.code, detail=detail)


class UserPortalUnavailableError(UserPortalError):
    """Unreachable, timed out, overloaded (5xx) or rate-limiting us (429)."""


class UserPortalAuthError(UserPortalError):
    """We couldn't get a token, or the portal rejected it (401) or its scopes (403)."""


class UserPortalContractError(UserPortalError):
    """The portal rejected our request as malformed, or replied with something we don't accept."""


def parse_portal_response[M: BaseModel](model: type[M], data: Any) -> M:
    """Validate User Portal response data into one of our models."""
    try:
        return model.model_validate(data)
    except ValidationError as err:
        raise UserPortalContractError(f"Unexpected response from user portal: {err}") from err


def _decode(response: httpx.Response) -> Any:
    """The JSON body of a successful response, which the portal promised."""
    try:
        return response.json()
    except ValueError as err:
        raise UserPortalContractError(f"User portal sent a body that isn't JSON: {err}") from err


class _InviteFeedItem(BaseModel):
    """The fields of an invite that list_invites pages on; the rest pass through."""

    model_config = ConfigDict(extra="allow")

    invite_id: str
    updated_at: str


class _GroupMembersPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    members: list[dict[str, Any]]
    stale: bool


class _InviteFeedPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[_InviteFeedItem]


def _upstream_detail(response: httpx.Response) -> str:
    # The portal's own errors are {"detail": "<sentence>"}
    try:
        detail = response.json().get("detail")
    except ValueError, AttributeError:
        detail = None
    return detail if isinstance(detail, str) else (response.text or response.reason_phrase)


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    detail = _upstream_detail(response)
    match status:
        case HTTPStatus.NOT_FOUND:
            raise NotFoundError(detail=detail)
        case HTTPStatus.CONFLICT:
            raise DuplicateError(detail=detail)
        case HTTPStatus.UNAUTHORIZED | HTTPStatus.FORBIDDEN:
            raise UserPortalAuthError(f"User portal refused our credentials: {detail}", status)
        case HTTPStatus.TOO_MANY_REQUESTS:
            raise UserPortalUnavailableError(f"User portal is rate limiting us: {detail}", status)
        case _ if status >= 500:
            raise UserPortalUnavailableError(f"User portal error: {detail}", status)
        case _:
            raise UserPortalContractError(f"User portal rejected our request: {detail}", status)


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
    except httpx.RequestError as exc:
        raise UserPortalUnavailableError(f"Failed to contact user portal: {exc!r}") from exc

    _raise_for_status(response)
    return response


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

    @asynccontextmanager
    async def deadline(self, seconds: float = 30) -> AsyncGenerator[None]:
        """
        Bounds a group of calls, such as those that set up one proposal or panel while its
        ODA transaction is open, so a slow portal can't hold the transaction open for long.
        """
        try:
            async with asyncio.timeout(seconds):
                yield
        except TimeoutError as err:
            raise UserPortalUnavailableError(
                f"User portal calls took longer than {seconds}s"
            ) from err

    @staticmethod
    def _write_headers(acting_as: AuthContext, idempotent: bool = True) -> dict[str, str]:
        """Headers for state-changing calls: who we act on behalf of, and a per-call
        Idempotency-Key (required by the portal on POSTs)."""
        # The portal identifies (and records as owner) the acting user by their INDIGO
        # account id, the token's 'sub' claim -- not our user_id (preferred_username)
        # TODO: send acting_as.user_id once the portal accepts usernames in
        # X-Acting-User, and take a user_id here rather than the whole AuthContext
        headers = {"X-Acting-User": acting_as.token_claims["sub"]}
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
        except UserPortalAuthError as exc:
            if exc.upstream_status != HTTPStatus.UNAUTHORIZED:
                raise
        # Our token was rejected (revoked, or expired early), so get a new one and retry once
        self.tokens.invalidate()
        try:
            return await self._send(method, url, headers, params=params, json=json)
        except UserPortalAuthError as exc:
            if exc.upstream_status == HTTPStatus.UNAUTHORIZED:
                self.tokens.invalidate()
            raise

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
            raise UserPortalAuthError("Unable to get an access token for the user portal") from err
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
        return _decode(response)

    async def _create_entity_groups(
        self,
        skuid: ShortSkuid,
        acting_as: AuthContext,
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
            await self.create_group(name, acting_as, desc)
        return names

    async def create_proposal_groups(
        self, prsl_id: ShortSkuid[Literal[et.PRP]], acting_as: AuthContext
    ) -> ProposalGroupsTuple:
        read, write, admin = await self._create_entity_groups(
            prsl_id,
            acting_as,
            read_desc=f"Collaborators on proposal ({prsl_id})",
            write_desc=f"Co-Investigators with edit rights on proposal ({prsl_id})",
            admin_desc=f"Principal Investigator(s) for proposal ({prsl_id})",
        )
        return ProposalGroupsTuple(read=read, write=write, admin=admin)

    async def create_panel_groups(
        self, pnl_id: ShortSkuid[Literal[et.PNL]], acting_as: AuthContext
    ) -> PanelGroupsTuple:
        read, _, admin = await self._create_entity_groups(
            pnl_id,
            acting_as,
            read_desc=f"Members of panel ({pnl_id})",
            write_desc=f"UNUSED middle tier of panel membership ({pnl_id})",
            admin_desc=f"Chair(s) of panel ({pnl_id})",
        )
        return PanelGroupsTuple(read=read, admin=admin)

    async def create_group(
        self, group_name: str, acting_as: AuthContext, description: str = ""
    ) -> dict[str, Any]:
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups",
            json={"group_name": group_name, "display_name": description},
            extra_headers=self._write_headers(acting_as),
        )
        return _decode(response)

    async def create_membership(
        self,
        group_name: str,
        user_id: str,
        acting_as: AuthContext,
    ) -> dict[str, Any]:
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/members",
            # Our user_id is the Indigo userName, which the portal calls preferred_username
            json={"preferred_username": user_id},
            extra_headers=self._write_headers(acting_as),
        )
        return _decode(response)

    async def list_group_members(self, group_name: str) -> dict[str, Any]:
        response = await self._call(
            method="GET",
            url=f"{self.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/members",
            params={"include_user_info": True},
        )
        payload = _decode(response)
        # Checked here so callers can index it; each member is checked as it's parsed
        parse_portal_response(_GroupMembersPage, payload)
        return payload

    async def create_invite(
        self,
        prsl_id: ShortSkuid[Literal[et.PRP]],
        invite_payload: dict[str, Any],
        acting_as: AuthContext,
    ) -> dict[str, Any]:
        group_name = get_group_name(prsl_id)
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/invites",
            json=invite_payload,
            extra_headers=self._write_headers(acting_as),
        )
        return _decode(response)

    async def create_invites(
        self,
        prsl_id: ShortSkuid[Literal[et.PRP]],
        invite_payloads: list[dict[str, Any]],
        acting_as: AuthContext,
    ) -> dict[str, Any]:
        """Create up to 100 invites, which the portal reports on one by one."""
        group_name = quote(get_group_name(prsl_id), safe="")
        response = await self._call(
            method="POST",
            url=f"{self.base_url}/api/external/v1/groups/{group_name}/invites/bulk",
            json={"invites": invite_payloads},
            extra_headers=self._write_headers(acting_as),
        )
        return _decode(response)

    async def get_invite(self, invite_id: UUID) -> dict[str, Any]:
        response = await self._call(
            method="GET",
            url=f"{self.base_url}/api/external/v1/invites/{invite_id}",
        )
        return _decode(response)

    async def list_invites(self, prsl_id: ShortSkuid[Literal[et.PRP]]) -> list[dict[str, Any]]:
        """Every invite to the proposal, reading all pages of the portal's feed."""
        params: dict[str, Any] = {"group_name": get_group_name(prsl_id), "limit": INVITE_PAGE_SIZE}
        invites: dict[str, dict[str, Any]] = {}
        while True:
            response = await self._call(
                method="GET", url=f"{self.base_url}/api/external/v1/invites", params=params
            )
            page = [
                item.model_dump()
                for item in parse_portal_response(_InviteFeedPage, _decode(response)).items
            ]
            new = [item for item in page if item["invite_id"] not in invites]
            # A later copy of an invite is a newer version of it
            invites.update((item["invite_id"], item) for item in page)
            # The feed is oldest first, and a page can run past the limit. updated_since
            # is inclusive, so the next page repeats the last page's newest rows.
            if len(page) < INVITE_PAGE_SIZE or not new:
                return list(invites.values())
            params = {**params, "updated_since": max(item["updated_at"] for item in page)}

    async def delete_invite(self, invite_id: UUID, acting_as: AuthContext) -> dict[str, Any]:
        response = await self._call(
            method="DELETE",
            url=f"{self.base_url}/api/external/v1/invites/{invite_id}",
            extra_headers=self._write_headers(acting_as, idempotent=False),
        )
        return _decode(response)
