"""
Access tokens for calling other services as ourselves (not on behalf of a user).

ClientCredentialsTokenProvider performs an OAuth2 client-credentials grant and
caches the resulting token, fetching a new one only when the cached token is
close to expiry. Like ska_aaa_authhelpers' KeysetFetcher, refresh happens on
demand rather than on a timer, and a still-valid cached token is preferred over
failing outright if a refresh attempt errors.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

LOGGER = logging.getLogger(__name__)

# Refresh this long before the token actually expires, so a token we hand out
# doesn't expire while the request using it is in flight.
DEFAULT_REFRESH_MARGIN = timedelta(seconds=60)
# expires_in is only RECOMMENDED by RFC 6749, so assume a short lifetime if it's missing.
DEFAULT_TOKEN_LIFETIME = timedelta(minutes=5)


class TokenError(Exception):
    """Unable to obtain an access token."""


@dataclass(frozen=True)
class _CachedToken:
    value: str
    expires_at: datetime


class ClientCredentialsTokenProvider:
    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        *,
        scope: str | None = None,
        audience: str | None = None,
        timeout: float = 10,
        refresh_margin: timedelta = DEFAULT_REFRESH_MARGIN,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self._client_secret = client_secret
        self.scope = scope
        self.audience = audience
        self.timeout = timeout
        self.refresh_margin = refresh_margin
        self._transport = transport
        self._cached: _CachedToken | None = None
        # Serialises refreshes so concurrent requests share one grant
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _is_fresh(self, token: _CachedToken | None) -> bool:
        return token is not None and self._now() < token.expires_at - self.refresh_margin

    def _is_unexpired(self, token: _CachedToken | None) -> bool:
        return token is not None and self._now() < token.expires_at

    async def get_token(self) -> str:
        if self._is_fresh(self._cached):
            return self._cached.value

        async with self._lock:
            # Another caller may have refreshed while we waited for the lock
            if not self._is_fresh(self._cached):
                self._cached = await self._fetch_or_fallback()
            return self._cached.value

    def invalidate(self) -> None:
        """Discard the cached token, e.g. after the upstream rejects it."""
        self._cached = None

    async def _fetch_or_fallback(self) -> _CachedToken:
        try:
            return await self._fetch()
        except TokenError:
            if self._is_unexpired(self._cached):
                LOGGER.warning(
                    "Token refresh from %s failed; reusing cached token until it expires",
                    self.token_url,
                )
                return self._cached
            raise

    async def _fetch(self) -> _CachedToken:
        LOGGER.debug("Requesting client-credentials token from %s", self.token_url)
        data = {"grant_type": "client_credentials"}
        if self.scope:
            data["scope"] = self.scope
        if self.audience:
            data["audience"] = self.audience

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    auth=(self.client_id, self._client_secret),
                )
            response.raise_for_status()
            body = response.json()
            access_token = body["access_token"]
            expires_in = body.get("expires_in")
            lifetime = (
                timedelta(seconds=int(expires_in))
                if expires_in is not None
                else DEFAULT_TOKEN_LIFETIME
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as err:
            # Don't include the response body: on success it would contain the token
            LOGGER.exception("Failed to get access token from %s", self.token_url)
            raise TokenError(f"Unable to get access token from {self.token_url}") from err

        return _CachedToken(value=access_token, expires_at=self._now() + lifetime)
