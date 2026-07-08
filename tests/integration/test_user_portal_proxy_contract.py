from http import HTTPStatus
from uuid import uuid4

import httpx
from fastapi import HTTPException

from ska_oso_services.pht.service import user_portal
from tests.integration.conftest import PHT_BASE_URL


def test_search_users_happy_path_proxies_to_user_portal(integration_client):
    response = integration_client.get(
        f"{PHT_BASE_URL}/users/search",
        params={"q": "alice", "limit": 5},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_create_invite_by_user_id_happy_path(integration_client):
    prsl_id = "prp-000001"
    response = integration_client.post(
        f"{PHT_BASE_URL}/proposals/{prsl_id}/invites",
        json={"user_id": str(uuid4())},
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert "invite_id" in payload
    assert payload.get("group_name") == f"app:pht:{prsl_id}"


def test_create_invite_by_email_happy_path(integration_client):
    prsl_id = "prp-000002"
    response = integration_client.post(
        f"{PHT_BASE_URL}/proposals/{prsl_id}/invites",
        json={"email": "new-user@example.org"},
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert "invite_id" in payload
    assert payload.get("group_name") == f"app:pht:{prsl_id}"


def test_list_invites_by_proposal_happy_path(integration_client):
    response = integration_client.get(f"{PHT_BASE_URL}/proposals/prp-000003/invites")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


def test_delete_invite_happy_path(integration_client):
    invite_id = uuid4()
    response = integration_client.delete(
        f"{PHT_BASE_URL}/proposals/prp-000004/invites/{invite_id}"
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json().get("status")


def test_search_users_no_results_returns_empty_list(integration_client):
    response = integration_client.get(
        f"{PHT_BASE_URL}/users/search",
        params={"q": "zzzz-no-user-expected"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"results": []}


def test_search_users_upstream_502_maps_to_bad_gateway(integration_client, monkeypatch):
    async def fake_upstream_request(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail="upstream unavailable")

    monkeypatch.setattr(user_portal, "call_user_portal", fake_upstream_request)

    response = integration_client.get(
        f"{PHT_BASE_URL}/users/search",
        params={"q": "alice"},
    )

    assert response.status_code == HTTPStatus.BAD_GATEWAY


def test_create_invite_invalid_payload_returns_422(integration_client):
    response = integration_client.post(
        f"{PHT_BASE_URL}/proposals/prp-000005/invites",
        json={},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
