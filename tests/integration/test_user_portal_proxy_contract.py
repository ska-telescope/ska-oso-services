import asyncio
from http import HTTPStatus
from unittest.mock import ANY, AsyncMock
from urllib.parse import quote
from uuid import uuid4

from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.security.facts import get_group_skuid
from ska_oso_services.pht.service.user_portal import UserPortalService, UserPortalUnavailableError
from tests.conftest import PHT_BASE_API_URL
from tests.integration.conftest import MOCK_GROUP_NAME


def test_search_users_happy_path_proxies_to_user_portal(integration_client):
    response = integration_client.get(
        f"{PHT_BASE_API_URL}/users/search",
        params={"q": "alice", "limit": 5},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "results" in payload
    assert isinstance(payload["results"], list)
    if payload["results"]:
        first_result = payload["results"][0]
        assert "user_id" in first_result
        assert not {"portal_user_id", "preferred_username"} & first_result.keys()


def test_create_invite_by_user_id_is_rejected(integration_client):
    # Invites are by email only; the portal resolves known accounts from the address
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/prp-1/invites",
        json={"invites": [{"user_id": "someone"}]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_invite_by_email_happy_path(integration_client):
    prsl_id = "prp-2"
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/{prsl_id}/invites",
        json={"invites": [{"email": "new-user@example.org"}]},
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert isinstance(payload, dict)
    assert "invites" in payload
    assert isinstance(payload["invites"], list)
    assert len(payload["invites"]) == 1
    assert "invite_id" in payload["invites"][0]
    assert isinstance(payload["invites"][0].get("group_name"), str)


def test_create_invites_bulk_happy_path(integration_client):
    prsl_id = "prp-6"
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/{prsl_id}/invites",
        json={
            "invites": [
                {"email": "bulk-user-1@example.org"},
                {"email": "bulk-user-2@example.org"},
            ]
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert isinstance(payload, dict)
    assert "invites" in payload
    assert isinstance(payload["invites"], list)
    assert len(payload["invites"]) == 2
    assert all("invite_id" in item for item in payload["invites"])


def test_list_invites_by_proposal_happy_path(integration_client):
    response = integration_client.get(f"{PHT_BASE_API_URL}/prsls/prp-3/invites")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "invites" in payload
    assert isinstance(payload["invites"], list)


def test_list_members_happy_path(integration_client):
    response = integration_client.get(f"{PHT_BASE_API_URL}/prsls/prp-1/members")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert isinstance(payload["stale"], bool)
    assert isinstance(payload["members"], list)
    for member in payload["members"]:
        assert "user_id" in member
        assert not {"iam_user_id", "portal_user_id", "preferred_username"} & member.keys()
        assert {"has_write", "is_admin"} <= member.keys()


def test_delete_invite_happy_path(integration_client):
    invite_id = uuid4()
    # The mocked invite always belongs to MOCK_GROUP_NAME, so target that proposal
    prsl_id = get_group_skuid(MOCK_GROUP_NAME)
    response = integration_client.delete(f"{PHT_BASE_API_URL}/prsls/{prsl_id}/invites/{invite_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json().get("status")


def test_delete_invite_for_other_proposal_returns_404(integration_client):
    invite_id = uuid4()
    response = integration_client.delete(f"{PHT_BASE_API_URL}/prsls/prp-123/invites/{invite_id}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_search_users_passes_upstream_results(integration_client):
    response = integration_client.get(
        f"{PHT_BASE_API_URL}/users/search",
        params={"q": "zzzz-no-user-expected"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_search_users_upstream_502_maps_to_bad_gateway(integration_client, monkeypatch):
    async def fake_upstream_request(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise UserPortalUnavailableError("upstream unavailable", HTTPStatus.SERVICE_UNAVAILABLE)

    monkeypatch.setattr(user_portal, "call_user_portal", fake_upstream_request)

    response = integration_client.get(
        f"{PHT_BASE_API_URL}/users/search",
        params={"q": "alice"},
    )

    assert response.status_code == HTTPStatus.BAD_GATEWAY


def test_create_invite_invalid_payload_returns_422(integration_client):
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/prp-5/invites",
        json={"invites": []},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_service_create_groups_happy_path(fake_user_portal):
    del fake_user_portal
    prsl_id = "prp-7"
    service = UserPortalService(x_request_id="integration-trace-id")
    group_name = user_portal.get_group_name(prsl_id)

    payload = asyncio.run(service.create_group(group_name, str(uuid4()), description=prsl_id))

    # Prism mocks the schema, not the request, so it returns the injected example
    # rather than echoing our group_name back.
    assert payload["group_name"] == MOCK_GROUP_NAME
    assert isinstance(payload["display_name"], str)


def test_service_create_memberships_happy_path(fake_user_portal):
    del fake_user_portal
    prsl_id = "prp-8"
    user_id = str(uuid4())
    acting_user = str(uuid4())
    service = UserPortalService(x_request_id="integration-trace-id")
    group_name = user_portal.get_group_name(prsl_id)
    expected_payload = {"status": "ok"}
    mock_call = AsyncMock(return_value=type("Resp", (), {"json": lambda self: expected_payload})())

    original_call = user_portal.call_user_portal
    user_portal.call_user_portal = mock_call

    try:
        payload = asyncio.run(
            service.create_membership(
                group_name=group_name,
                user_id=user_id,
                acting_user=acting_user,
            )
        )
    finally:
        user_portal.call_user_portal = original_call

    assert payload == expected_payload
    mock_call.assert_awaited_once_with(
        method="POST",
        url=(f"{service.base_url}/api/external/v1/groups/{quote(group_name, safe='')}/members"),
        params=None,
        json={"preferred_username": user_id},
        headers=ANY,
        timeout=service.timeout,
    )
    headers = mock_call.await_args.kwargs["headers"]
    assert headers["X-Acting-User"] == acting_user
    assert headers["Idempotency-Key"]
