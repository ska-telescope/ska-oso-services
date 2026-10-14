import asyncio
import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
import pytest

from ska_oso_services.common.client_credentials import (
    DEFAULT_TOKEN_LIFETIME,
    ClientCredentialsTokenProvider,
    TokenError,
)

TOKEN_URL = "https://iam.example.org/token"
CLIENT_ID = "test-client"
CLIENT_SECRET = "test-secret"  # noqa: S105
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeIndigo:
    """Token endpoint stand-in that hands out token-1, token-2, ... and records requests."""

    def __init__(self, expires_in: int | None = 300) -> None:
        self.expires_in = expires_in
        self.requests: list[httpx.Request] = []
        self.fail = False
        self.delay = 0.0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            return httpx.Response(503)
        body = {"access_token": f"token-{len(self.requests)}", "token_type": "Bearer"}
        if self.expires_in is not None:
            body["expires_in"] = self.expires_in
        return httpx.Response(200, json=body)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def indigo() -> FakeIndigo:
    return FakeIndigo()


@pytest.fixture
def clock() -> Clock:
    return Clock()


def make_provider(indigo, clock, **kwargs) -> ClientCredentialsTokenProvider:
    provider = ClientCredentialsTokenProvider(
        TOKEN_URL,
        CLIENT_ID,
        CLIENT_SECRET,
        transport=httpx.MockTransport(indigo),
        **kwargs,
    )
    provider._now = clock  # pylint: disable=protected-access
    return provider


async def test_requests_client_credentials_grant(indigo, clock):
    provider = make_provider(indigo, clock, scope="portal:read portal:write", audience="portal")

    assert await provider.get_token() == "token-1"

    (request,) = indigo.requests
    assert request.method == "POST"
    assert str(request.url) == TOKEN_URL
    assert parse_qs(request.content.decode()) == {
        "grant_type": ["client_credentials"],
        "scope": ["portal:read portal:write"],
        "audience": ["portal"],
    }
    expected_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    assert request.headers["Authorization"] == f"Basic {expected_auth}"


async def test_omits_scope_and_audience_when_not_configured(indigo, clock):
    provider = make_provider(indigo, clock)

    await provider.get_token()

    assert parse_qs(indigo.requests[0].content.decode()) == {"grant_type": ["client_credentials"]}


async def test_reuses_cached_token_until_refresh_margin(indigo, clock):
    provider = make_provider(indigo, clock, refresh_margin=timedelta(seconds=60))

    assert await provider.get_token() == "token-1"
    clock.advance(seconds=239)  # expires_in=300, so 61s left: still outside the margin
    assert await provider.get_token() == "token-1"
    assert len(indigo.requests) == 1


async def test_refreshes_once_within_refresh_margin(indigo, clock):
    provider = make_provider(indigo, clock, refresh_margin=timedelta(seconds=60))

    await provider.get_token()
    clock.advance(seconds=241)  # 59s left
    assert await provider.get_token() == "token-2"
    assert len(indigo.requests) == 2


async def test_assumes_default_lifetime_without_expires_in(clock):
    indigo = FakeIndigo(expires_in=None)
    provider = make_provider(indigo, clock, refresh_margin=timedelta(0))

    await provider.get_token()
    clock.advance(seconds=DEFAULT_TOKEN_LIFETIME.total_seconds() - 1)
    assert await provider.get_token() == "token-1"
    clock.advance(seconds=1)
    assert await provider.get_token() == "token-2"


async def test_concurrent_callers_share_a_single_grant(indigo, clock):
    indigo.delay = 0.01
    provider = make_provider(indigo, clock)

    tokens = await asyncio.gather(*(provider.get_token() for _ in range(5)))

    assert tokens == ["token-1"] * 5
    assert len(indigo.requests) == 1


async def test_invalidate_forces_a_new_grant(indigo, clock):
    provider = make_provider(indigo, clock)

    await provider.get_token()
    provider.invalidate()

    assert await provider.get_token() == "token-2"


async def test_failed_refresh_reuses_unexpired_cached_token(indigo, clock):
    provider = make_provider(indigo, clock, refresh_margin=timedelta(seconds=60))
    await provider.get_token()

    clock.advance(seconds=270)  # inside the refresh margin, but not yet expired
    indigo.fail = True

    assert await provider.get_token() == "token-1"


async def test_failed_refresh_raises_once_cached_token_expired(indigo, clock):
    provider = make_provider(indigo, clock)
    await provider.get_token()

    clock.advance(seconds=300)
    indigo.fail = True

    with pytest.raises(TokenError):
        await provider.get_token()


async def test_failed_first_fetch_raises(indigo, clock):
    indigo.fail = True
    provider = make_provider(indigo, clock)

    with pytest.raises(TokenError):
        await provider.get_token()


async def test_recovers_after_failure(indigo, clock):
    indigo.fail = True
    provider = make_provider(indigo, clock)
    with pytest.raises(TokenError):
        await provider.get_token()

    indigo.fail = False

    assert await provider.get_token() == "token-2"


@pytest.mark.parametrize(
    "body",
    [
        {"token_type": "Bearer"},  # no access_token
        {"access_token": "t", "expires_in": "soon"},  # unparseable lifetime
    ],
)
async def test_malformed_token_response_raises(clock, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    provider = ClientCredentialsTokenProvider(
        TOKEN_URL, CLIENT_ID, CLIENT_SECRET, transport=transport
    )
    provider._now = clock  # pylint: disable=protected-access

    with pytest.raises(TokenError):
        await provider.get_token()


async def test_connection_error_raises_token_error(clock):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    provider = ClientCredentialsTokenProvider(
        TOKEN_URL, CLIENT_ID, CLIENT_SECRET, transport=httpx.MockTransport(refuse)
    )

    with pytest.raises(TokenError):
        await provider.get_token()
