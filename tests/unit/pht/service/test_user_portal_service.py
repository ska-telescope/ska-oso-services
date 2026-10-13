from http import HTTPStatus
from unittest import mock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from ska_oso_services.common.client_credentials import (
    ClientCredentialsTokenProvider,
    StaticTokenProvider,
    TokenError,
)
from ska_oso_services.pht.service import user_portal
from ska_oso_services.settings import UserPortalConfig

BASE_URL = "http://portal.example.org"


class FakeTokens:
    def __init__(self, *tokens: str | Exception) -> None:
        self._tokens = list(tokens)
        self.invalidated = 0

    async def get_token(self) -> str:
        token = self._tokens.pop(0)
        if isinstance(token, Exception):
            raise token
        return token

    def invalidate(self) -> None:
        self.invalidated += 1


def unauthorized():
    return HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="invalid token")


def ok(payload=None):
    return httpx.Response(200, json=payload or {"results": []})


@pytest.fixture
def make_service():
    def _make(tokens: FakeTokens) -> user_portal.UserPortalService:
        with mock.patch.object(user_portal, "get_token_provider", return_value=tokens):
            return user_portal.UserPortalService(x_request_id="trace-id")

    return _make


@pytest.fixture
def portal_call():
    with mock.patch.object(user_portal, "call_user_portal", new_callable=mock.AsyncMock) as call:
        yield call


class TestTokenHandling:
    async def test_sends_provider_token_as_bearer(self, make_service, portal_call):
        portal_call.return_value = ok()
        service = make_service(FakeTokens("token-1"))

        await service.search_users("alice", 5)

        headers = portal_call.await_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer token-1"

    async def test_401_invalidates_and_retries_with_new_token(self, make_service, portal_call):
        portal_call.side_effect = [unauthorized(), ok({"results": ["alice"]})]
        tokens = FakeTokens("stale", "fresh")
        service = make_service(tokens)

        assert await service.search_users("alice", 5) == {"results": ["alice"]}

        assert tokens.invalidated == 1
        sent = [c.kwargs["headers"]["Authorization"] for c in portal_call.await_args_list]
        assert sent == ["Bearer stale", "Bearer fresh"]

    async def test_retry_reuses_idempotency_key(self, make_service, portal_call):
        portal_call.side_effect = [unauthorized(), ok({"group_name": "app:pht:prp-1"})]
        service = make_service(FakeTokens("stale", "fresh"))

        await service.create_group("app:pht:prp-1", acting_user="user-1")

        first, second = (c.kwargs["headers"] for c in portal_call.await_args_list)
        assert first["Idempotency-Key"] == second["Idempotency-Key"]
        assert second["X-Acting-User"] == "user-1"

    async def test_repeated_401_becomes_bad_gateway(self, make_service, portal_call):
        portal_call.side_effect = [unauthorized(), unauthorized()]
        tokens = FakeTokens("stale", "also-rejected")
        service = make_service(tokens)

        with pytest.raises(HTTPException) as exc_info:
            await service.search_users("alice", 5)

        # The end user is authenticated fine; it's our credentials the portal rejected
        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        assert portal_call.await_count == 2

    async def test_other_errors_are_not_retried(self, make_service, portal_call):
        portal_call.side_effect = HTTPException(status_code=HTTPStatus.NOT_FOUND)
        tokens = FakeTokens("token-1")
        service = make_service(tokens)

        with pytest.raises(HTTPException) as exc_info:
            await service.search_users("alice", 5)

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND
        assert tokens.invalidated == 0
        assert portal_call.await_count == 1

    async def test_token_failure_becomes_bad_gateway(self, make_service, portal_call):
        service = make_service(FakeTokens(TokenError("IAM is down")))

        with pytest.raises(HTTPException) as exc_info:
            await service.search_users("alice", 5)

        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        portal_call.assert_not_awaited()


class TestGetTokenProvider:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        user_portal.get_token_provider.cache_clear()
        yield
        user_portal.get_token_provider.cache_clear()

    def _settings(self, **portal_kwargs):
        config = UserPortalConfig(base_url=BASE_URL, **portal_kwargs)
        return mock.patch.object(
            user_portal, "get_settings", return_value=mock.Mock(userportal=config)
        )

    async def test_static_token_without_token_url(self):
        with self._settings(api_key="static-key"):
            provider = user_portal.get_token_provider()

        assert isinstance(provider, StaticTokenProvider)
        assert await provider.get_token() == "static-key"

    def test_client_credentials_with_token_url(self):
        with self._settings(
            token_url="https://iam.example.org/token",
            client_id="client",
            client_secret="secret",
            token_scope="portal:read",
            token_audience="portal",
        ):
            provider = user_portal.get_token_provider()

        assert isinstance(provider, ClientCredentialsTokenProvider)
        assert provider.token_url == "https://iam.example.org/token"
        assert provider.client_id == "client"
        assert provider.scope == "portal:read"
        assert provider.audience == "portal"

    def test_provider_is_shared_across_services(self):
        with self._settings(api_key="static-key"):
            first = user_portal.UserPortalService(x_request_id="a")
            second = user_portal.UserPortalService(x_request_id="b")

        assert first.tokens is second.tokens


class TestUserPortalConfig:
    def test_token_url_requires_client_credentials(self):
        with pytest.raises(ValidationError, match="USER_PORTAL_CLIENT_ID"):
            UserPortalConfig(base_url=BASE_URL, token_url="https://iam.example.org/token")

    def test_empty_optional_values_are_unset(self):
        config = UserPortalConfig(
            base_url=BASE_URL, token_url="", token_scope="", token_audience=""
        )

        assert config.token_url is None
        assert config.token_scope is None
        assert config.token_audience is None

    def test_client_secret_is_not_exposed_in_repr(self):
        config = UserPortalConfig(
            base_url=BASE_URL,
            token_url="https://iam.example.org/token",
            client_id="client",
            client_secret="super-secret",
        )

        assert "super-secret" not in repr(config)
