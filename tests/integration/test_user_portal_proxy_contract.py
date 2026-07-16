from http import HTTPStatus
from uuid import uuid4

from fastapi import HTTPException

from ska_oso_services.pht.service import user_portal
from tests.conftest import PHT_BASE_API_URL


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
        assert "portal_user_id" not in first_result


def test_create_invite_by_user_id_happy_path(integration_client):
    prsl_id = "prp-000001"
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/{prsl_id}/invites",
        json={"invites": [{"user_id": str(uuid4())}]},
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert isinstance(payload, dict)
    assert "invites" in payload
    assert isinstance(payload["invites"], list)
    assert len(payload["invites"]) == 1
    assert "invite_id" in payload["invites"][0]
    assert isinstance(payload["invites"][0].get("group_name"), str)


def test_create_invite_by_email_happy_path(integration_client):
    prsl_id = "prp-000002"
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
    prsl_id = "prp-000006"
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/{prsl_id}/invites",
        json={
            "invites": [
                {"user_id": str(uuid4())},
                {"email": "bulk-user@example.org"},
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
    response = integration_client.get(f"{PHT_BASE_API_URL}/prsls/prp-000003/invites")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert "invites" in payload
    assert isinstance(payload["invites"], list)


def test_delete_invite_happy_path(integration_client):
    invite_id = uuid4()
    response = integration_client.delete(
        f"{PHT_BASE_API_URL}/prsls/prp-000004/invites/{invite_id}"
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json().get("status")


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
        raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail="upstream unavailable")

    monkeypatch.setattr(user_portal, "call_user_portal", fake_upstream_request)

    response = integration_client.get(
        f"{PHT_BASE_API_URL}/users/search",
        params={"q": "alice"},
    )

    assert response.status_code == HTTPStatus.BAD_GATEWAY


def test_create_invite_invalid_payload_returns_422(integration_client):
    response = integration_client.post(
        f"{PHT_BASE_API_URL}/prsls/prp-000005/invites",
        json={"invites": []},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
