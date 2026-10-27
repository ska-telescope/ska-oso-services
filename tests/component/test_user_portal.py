# pylint: disable=missing-timeout
"""
The User Portal routes, against the Prism mock that pipeline test deployments
use in place of the real portal. The deployed app still does a real
client-credentials grant, so these also check its Vault wiring for the secret.
"""

from http import HTTPStatus
from uuid import uuid4

from . import PHT_URL

# The group_name example in the mock's spec, which every mocked invite belongs to
MOCK_GROUP_PRSL_ID = "prp-1"


def test_search_users(authrequests):
    response = authrequests.get(f"{PHT_URL}/users/search", params={"q": "alice", "limit": 5})

    assert response.status_code == HTTPStatus.OK, response.text
    results = response.json()["results"]
    assert isinstance(results, list)
    for result in results:
        assert "user_id" in result
        assert not {"portal_user_id", "preferred_username"} & result.keys()


def test_create_invite_by_email(authrequests):
    response = authrequests.post(
        f"{PHT_URL}/prsls/prp-2/invites",
        json={"invites": [{"email": "new-user@example.org"}]},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert len(payload["invites"]) == 1
    assert "invite_id" in payload["invites"][0]
    assert isinstance(payload["invites"][0]["group_name"], str)
    assert payload["failed"] == []


def test_create_invites_bulk(authrequests):
    response = authrequests.post(
        f"{PHT_URL}/prsls/prp-6/invites",
        json={
            "invites": [
                {"email": "bulk-user-1@example.org"},
                {"email": "bulk-user-2@example.org"},
            ]
        },
    )

    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert isinstance(payload["failed"], list)
    # Prism's static mock answers with one result whatever we send
    assert all("invite_id" in item for item in payload["invites"])


def test_create_invite_by_user_id_is_rejected(authrequests):
    # Invites are by email only; the portal resolves known accounts from the address
    response = authrequests.post(
        f"{PHT_URL}/prsls/prp-1/invites", json={"invites": [{"user_id": "someone"}]}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_invite_with_no_invites_is_rejected(authrequests):
    response = authrequests.post(f"{PHT_URL}/prsls/prp-5/invites", json={"invites": []})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_list_invites(authrequests):
    response = authrequests.get(f"{PHT_URL}/prsls/prp-3/invites")

    assert response.status_code == HTTPStatus.OK, response.text
    assert isinstance(response.json()["invites"], list)


def test_list_members(authrequests):
    response = authrequests.get(f"{PHT_URL}/prsls/prp-1/members")

    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert isinstance(payload["stale"], bool)
    for member in payload["members"]:
        assert "user_id" in member
        assert not {"iam_user_id", "portal_user_id", "preferred_username"} & member.keys()
        assert {"has_write", "is_admin"} <= member.keys()


def test_delete_invite(authrequests):
    response = authrequests.delete(f"{PHT_URL}/prsls/{MOCK_GROUP_PRSL_ID}/invites/{uuid4()}")

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["status"]


def test_delete_invite_for_other_proposal_is_not_found(authrequests):
    response = authrequests.delete(f"{PHT_URL}/prsls/prp-123/invites/{uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND
