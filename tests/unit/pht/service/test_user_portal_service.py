import asyncio
from http import HTTPStatus
from unittest import mock

import httpx
import pytest
from pydantic import ValidationError
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_services.common.client_credentials import ClientCredentialsTokenProvider, TokenError
from ska_oso_services.common.error_handling import DuplicateError, NotFoundError
from ska_oso_services.pht.models.invitations import UserSearchResponse
from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.user_portal import (
    UserPortalAuthError,
    UserPortalContractError,
    UserPortalError,
    UserPortalUnavailableError,
)
from ska_oso_services.settings import UserPortalConfig

BASE_URL = "http://portal.example.org"
TOKEN_URL = "https://iam.example.org/token"
# Captured at import, before the autouse fixture in tests/unit/conftest.py replaces it
real_get_token_provider = user_portal.get_token_provider


def portal_config(**overrides) -> UserPortalConfig:
    kwargs = {
        "base_url": BASE_URL,
        "token_url": TOKEN_URL,
        "client_id": "client",
        "client_secret": "secret",
        "token_scope": "portal:users.read",
        "token_audience": "test:portal",
    } | overrides
    return UserPortalConfig(**kwargs)


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


def auth_context() -> AuthContext:
    return AuthContext(
        user_id="indigo-username",
        principals=frozenset({"indigo-username"}),
        roles=frozenset({Role.ANY}),
        groups=frozenset(),
        scopes=frozenset({"pht:readwrite"}),
        audience="test:pht",
        token_claims={"sub": "indigo-sub", "preferred_username": "indigo-username"},
        access_token="test-token",
    )


def unauthorized():
    return UserPortalAuthError("invalid token", HTTPStatus.UNAUTHORIZED)


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

        await service.create_group("app:pht:prp-1", acting_as=auth_context())

        first, second = (c.kwargs["headers"] for c in portal_call.await_args_list)
        assert first["Idempotency-Key"] == second["Idempotency-Key"]
        assert second["X-Acting-User"] == "indigo-sub"

    async def test_acting_user_is_the_indigo_account_id(self, make_service, portal_call):
        # The portal resolves X-Acting-User as an INDIGO account id (and records it as
        # the group owner), so it must be the token's sub, not our user_id
        portal_call.return_value = ok({"group_name": "app:pht:prp-1"})
        service = make_service(FakeTokens("token-1"))

        await service.create_group("app:pht:prp-1", acting_as=auth_context())

        assert portal_call.await_args.kwargs["headers"]["X-Acting-User"] == "indigo-sub"

    async def test_repeated_401_becomes_bad_gateway(self, make_service, portal_call):
        portal_call.side_effect = [unauthorized(), unauthorized()]
        tokens = FakeTokens("stale", "also-rejected")
        service = make_service(tokens)

        with pytest.raises(UserPortalAuthError) as exc_info:
            await service.search_users("alice", 5)

        # The end user is authenticated fine; it's our credentials the portal rejected
        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        assert portal_call.await_count == 2
        assert tokens.invalidated == 2

    async def test_403_is_not_retried(self, make_service, portal_call):
        # Missing scope: a fresh token won't have it either
        portal_call.side_effect = UserPortalAuthError("missing scope", HTTPStatus.FORBIDDEN)
        tokens = FakeTokens("token-1")
        service = make_service(tokens)

        with pytest.raises(UserPortalAuthError):
            await service.search_users("alice", 5)

        assert tokens.invalidated == 0
        assert portal_call.await_count == 1

    async def test_other_errors_are_not_retried(self, make_service, portal_call):
        portal_call.side_effect = NotFoundError("no such invite")
        tokens = FakeTokens("token-1")
        service = make_service(tokens)

        with pytest.raises(NotFoundError):
            await service.search_users("alice", 5)

        assert tokens.invalidated == 0
        assert portal_call.await_count == 1

    async def test_token_failure_becomes_bad_gateway(self, make_service, portal_call):
        service = make_service(FakeTokens(TokenError("IAM is down")))

        with pytest.raises(UserPortalAuthError) as exc_info:
            await service.search_users("alice", 5)

        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        portal_call.assert_not_awaited()


@pytest.fixture
def portal_responds(monkeypatch):
    """Make call_user_portal's httpx client answer with the given response or error."""

    def _respond(result: httpx.Response | Exception):
        def handler(request):
            if isinstance(result, Exception):
                raise result
            return result

        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            user_portal.httpx,
            "AsyncClient",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
        )

    return _respond


async def call_portal():
    return await user_portal.call_user_portal("GET", f"{BASE_URL}/api/external/v1/invites", 5)


class TestPortalErrors:
    async def test_success_returns_response(self, portal_responds):
        portal_responds(httpx.Response(200, json={"items": []}))

        response = await call_portal()

        assert response.json() == {"items": []}

    @pytest.mark.parametrize(
        "status, error",
        [
            (HTTPStatus.UNAUTHORIZED, UserPortalAuthError),
            (HTTPStatus.FORBIDDEN, UserPortalAuthError),
            (HTTPStatus.TOO_MANY_REQUESTS, UserPortalUnavailableError),
            (HTTPStatus.INTERNAL_SERVER_ERROR, UserPortalUnavailableError),
            (HTTPStatus.SERVICE_UNAVAILABLE, UserPortalUnavailableError),
            (HTTPStatus.BAD_REQUEST, UserPortalContractError),
            (HTTPStatus.UNPROCESSABLE_ENTITY, UserPortalContractError),
        ],
    )
    async def test_portal_failures_are_bad_gateway(self, portal_responds, status, error):
        portal_responds(httpx.Response(status, json={"detail": "upstream says no"}))

        with pytest.raises(error) as exc_info:
            await call_portal()

        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        assert exc_info.value.upstream_status == status
        assert "upstream says no" in exc_info.value.detail

    @pytest.mark.parametrize(
        "status, error",
        [(HTTPStatus.NOT_FOUND, NotFoundError), (HTTPStatus.CONFLICT, DuplicateError)],
    )
    async def test_callers_request_errors_keep_their_status(self, portal_responds, status, error):
        # e.g. an unknown invite id, or inviting someone who already has a pending invite
        portal_responds(httpx.Response(status, json={"detail": "Invite already pending."}))

        with pytest.raises(error) as exc_info:
            await call_portal()

        assert exc_info.value.status_code == status
        assert exc_info.value.detail == "Invite already pending."

    async def test_non_json_error_body_is_reported(self, portal_responds):
        portal_responds(httpx.Response(HTTPStatus.BAD_GATEWAY, text="<html>proxy error</html>"))

        with pytest.raises(UserPortalUnavailableError) as exc_info:
            await call_portal()

        assert "proxy error" in exc_info.value.detail

    async def test_connection_failure_is_unavailable(self, portal_responds):
        portal_responds(httpx.ConnectError("connection refused"))

        with pytest.raises(UserPortalUnavailableError) as exc_info:
            await call_portal()

        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        assert exc_info.value.upstream_status is None

    async def test_errors_are_logged(self, portal_responds, caplog):
        portal_responds(httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE, json={"detail": "down"}))

        with pytest.raises(UserPortalError):
            await call_portal()

        assert "UserPortalUnavailableError" in caplog.text

    def test_unexpected_response_is_a_contract_error(self):
        # e.g. a "disabled" account without a preferred_username
        hit = {"preferred_username": None, "display_name": "Ada", "email": "ada@example.org"}

        with pytest.raises(UserPortalContractError) as exc_info:
            user_portal.parse_portal_response(UserSearchResponse, {"results": [hit]})

        assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
        assert "preferred_username" in exc_info.value.detail


class TestGetTokenProvider:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        real_get_token_provider.cache_clear()
        yield
        real_get_token_provider.cache_clear()

    def _settings(self, **overrides):
        config = portal_config(**overrides)
        return mock.patch.object(
            user_portal, "get_settings", return_value=mock.Mock(userportal=config)
        )

    def test_builds_provider_from_settings(self):
        with self._settings(token_scope="portal:users.read", token_audience="live:portal"):
            provider = real_get_token_provider()

        assert isinstance(provider, ClientCredentialsTokenProvider)
        assert provider.token_url == TOKEN_URL
        assert provider.client_id == "client"
        assert provider.scope == "portal:users.read"
        assert provider.audience == "live:portal"

    def test_provider_is_shared_across_requests(self):
        with self._settings():
            assert real_get_token_provider() is real_get_token_provider()


class TestUserPortalConfig:
    @pytest.mark.parametrize(
        "field", ["token_url", "client_id", "client_secret", "token_scope", "token_audience"]
    )
    def test_client_credentials_are_required(self, field):
        kwargs = {
            "base_url": BASE_URL,
            "token_url": TOKEN_URL,
            "client_id": "client",
            "client_secret": "secret",
            "token_scope": "portal:users.read",
            "token_audience": "test:portal",
        }
        del kwargs[field]

        # Bypass the USER_PORTAL_* defaults that tests/conftest.py puts in the environment
        with mock.patch.dict("os.environ", clear=True):
            with pytest.raises(ValidationError):
                UserPortalConfig(**kwargs)

    @pytest.mark.parametrize(
        "field", ["client_id", "client_secret", "token_scope", "token_audience"]
    )
    def test_client_credentials_must_not_be_empty(self, field):
        with pytest.raises(ValidationError):
            portal_config(**{field: ""})

    def test_client_secret_is_not_exposed_in_repr(self):
        assert "super-secret" not in repr(portal_config(client_secret="super-secret"))


def _invite(invite_id: str, updated_at: str) -> dict:
    return {"invite_id": invite_id, "updated_at": updated_at}


class TestListInvites:
    @pytest.fixture(autouse=True)
    def small_pages(self, monkeypatch):
        monkeypatch.setattr(user_portal, "INVITE_PAGE_SIZE", 2)

    async def test_reads_every_page(self, make_service, portal_call):
        portal_call.side_effect = [
            ok({"items": [_invite("a", "T1"), _invite("b", "T2")]}),
            # updated_since is inclusive, so "b" comes back too
            ok({"items": [_invite("b", "T2"), _invite("c", "T3")]}),
            ok({"items": [_invite("c", "T3")]}),
        ]
        service = make_service(FakeTokens(*["token"] * 3))

        invites = await service.list_invites("prp-1")

        assert [i["invite_id"] for i in invites] == ["a", "b", "c"]
        since = [c.kwargs["params"].get("updated_since") for c in portal_call.await_args_list]
        assert since == [None, "T2", "T3"]

    async def test_keeps_the_newest_copy_of_an_invite(self, make_service, portal_call):
        portal_call.side_effect = [
            ok({"items": [_invite("a", "T1"), _invite("b", "T2")]}),
            ok({"items": [_invite("b", "T2"), {**_invite("a", "T3"), "claim_state": "revoked"}]}),
            ok({"items": [{**_invite("a", "T3"), "claim_state": "revoked"}]}),
        ]
        service = make_service(FakeTokens(*["token"] * 3))

        invites = {i["invite_id"]: i for i in await service.list_invites("prp-1")}

        assert invites["a"]["claim_state"] == "revoked"

    async def test_stops_when_a_full_page_has_nothing_new(self, make_service, portal_call):
        # A block of rows sharing one updated_at comes back whole, so a full page of
        # rows already seen is the end of the feed rather than a reason to loop
        same = ok({"items": [_invite("a", "T1"), _invite("b", "T1")]})
        portal_call.side_effect = [same, same]
        service = make_service(FakeTokens(*["token"] * 3))

        assert len(await service.list_invites("prp-1")) == 2
        assert portal_call.await_count == 2


class TestDeadline:
    async def test_a_slow_setup_is_unavailable(self, make_service):
        service = make_service(FakeTokens())
        with pytest.raises(UserPortalUnavailableError, match="longer than"):
            async with service.deadline(0.01):
                await asyncio.sleep(1)

    async def test_a_quick_setup_is_untouched(self, make_service):
        service = make_service(FakeTokens())

        async with service.deadline():
            await asyncio.sleep(0)


class TestMalformedResponses:
    async def test_a_body_that_is_not_json_is_a_contract_error(self, make_service, portal_call):
        portal_call.return_value = httpx.Response(200, text="<html>oops</html>")
        service = make_service(FakeTokens("token"))

        with pytest.raises(UserPortalContractError, match="isn't JSON"):
            await service.search_users("alice", 5)

    @pytest.mark.parametrize(
        "body",
        [{}, {"items": [{"invite_id": "a"}]}, {"items": [{"updated_at": "T1"}]}],
    )
    async def test_an_invite_page_missing_fields_is_a_contract_error(
        self, make_service, portal_call, body
    ):
        portal_call.return_value = ok(body)
        service = make_service(FakeTokens("token"))

        with pytest.raises(UserPortalContractError):
            await service.list_invites("prp-1")

    async def test_invite_fields_pass_through(self, make_service, portal_call):
        item = {"invite_id": "a", "updated_at": "T1", "claim_state": "pending"}
        portal_call.return_value = ok({"items": [item]})
        service = make_service(FakeTokens("token"))

        assert await service.list_invites("prp-1") == [item]

    @pytest.mark.parametrize("body", [{"members": []}, {"stale": False}])
    async def test_a_member_list_missing_fields_is_a_contract_error(
        self, make_service, portal_call, body
    ):
        portal_call.return_value = ok(body)
        service = make_service(FakeTokens("token"))

        with pytest.raises(UserPortalContractError):
            await service.list_group_members("app:pht:prp-1")


class TestCreateMembership:
    async def test_adds_the_user_by_indigo_username(self, make_service, portal_call):
        portal_call.return_value = ok({"status": "ok"})
        service = make_service(FakeTokens("token"))

        assert await service.create_membership(
            "app:pht:prp-1/w", user_id="indigo-username", acting_as=auth_context()
        ) == {"status": "ok"}

        kwargs = portal_call.await_args.kwargs
        assert kwargs["method"] == "POST"
        # The group name is one path segment, so its slash is escaped
        assert (
            kwargs["url"]
            == f"{service.base_url}/api/external/v1/groups/app%3Apht%3Aprp-1%2Fw/members"
        )
        assert kwargs["json"] == {"preferred_username": "indigo-username"}
        assert kwargs["headers"]["Idempotency-Key"]
