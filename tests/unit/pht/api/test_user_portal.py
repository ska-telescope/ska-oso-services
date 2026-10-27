"""
Unit tests for ska_oso_services.pht.api.user_portal
"""

from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import AsyncMock, create_autospec, patch
from uuid import uuid4

import pytest
from ska_aaa_authhelpers import AuthContext, AuthFailError, Role

from ska_oso_services.common.error_handling import NotFoundError
from ska_oso_services.pht.api.user_portal import create_invites, delete_invite, list_members
from ska_oso_services.pht.models.invitations import InviteCreateListRequest
from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.security import SecurityService
from ska_oso_services.pht.service.user_portal import (
    UserPortalContractError,
    UserPortalUnavailableError,
)
from tests.conftest import PHT_BASE_API_URL

PRSL_ID = "prp-abc123"
OTHER_PRSL_ID = "prp-zzz999"
USER_ID = "a1baebc7-2d1a-4a35-ac07-478d2fc6af95"
# The INDIGO account id ('sub'), which the portal needs as X-Acting-User; not our user_id
USER_SUB = "6c0e7d1e-5f0b-4a43-9b1a-0d6a2f1d9c11"


def _invite_card(group_name: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "invite_id": str(uuid4()),
        "group_name": group_name,
        "invited_email": "someone@example.org",
        "invited_by": "pi@example.org",
        "claim_state": "pending",
        "claimed_by_portal_user_id": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": now,
    }


def _pi_security(prsl_id: str) -> SecurityService:
    group = f"app:pht:{prsl_id}/w/a"
    auth = AuthContext(
        user_id=USER_ID,
        principals=frozenset({group, USER_ID}),
        roles=frozenset({Role.ANY}),
        groups=frozenset({group}),
        scopes=frozenset({"pht:readwrite"}),
        audience="test:pht",
        token_claims={"sub": USER_SUB, "preferred_username": USER_ID},
        access_token="test-token",
    )
    return SecurityService(auth)


class TestCreateInvites:
    async def test_one_failure_does_not_stop_the_others(self):
        service = create_autospec(user_portal.UserPortalService, instance=True)
        created = _invite_card(group_name=f"app:pht:{PRSL_ID}")
        service.create_invites.return_value = {
            "created": 1,
            "failed": 1,
            "results": [
                {"index": 0, "status": "duplicate", "email": "a@example.org", "detail": "dup"},
                {"index": 1, "status": "created", "email": "b@example.org", "invite": created},
            ],
        }
        security = _pi_security(PRSL_ID)
        body = InviteCreateListRequest(
            invites=[{"email": "a@example.org"}, {"email": "b@example.org"}]
        )

        response = await create_invites(
            security=security, service=service, prsl_id=PRSL_ID, body=body
        )

        service.create_invites.assert_awaited_once_with(
            prsl_id=PRSL_ID,
            invite_payloads=[{"email": "a@example.org"}, {"email": "b@example.org"}],
            acting_as=security.auth,
        )
        assert [str(i.invite_id) for i in response.invites] == [created["invite_id"]]
        assert [(f.email, f.status) for f in response.failed] == [("a@example.org", "duplicate")]


class TestDeleteInvite:
    async def test_delete_invite_for_other_proposal_returns_404(self):
        """A PI of PRSL_ID must not be able to delete an invite belonging to another proposal."""
        service = create_autospec(user_portal.UserPortalService, instance=True)
        service.get_invite.return_value = _invite_card(group_name=f"app:pht:{OTHER_PRSL_ID}")

        with pytest.raises(NotFoundError):
            await delete_invite(
                security=_pi_security(PRSL_ID),
                service=service,
                prsl_id=PRSL_ID,
                invite_id=uuid4(),
            )

    async def test_delete_invite_matching_base_group_succeeds(self):
        service = create_autospec(user_portal.UserPortalService, instance=True)
        service.get_invite.return_value = _invite_card(group_name=f"app:pht:{PRSL_ID}")
        service.delete_invite.return_value = {"status": "deleted"}
        invite_id = uuid4()

        security = _pi_security(PRSL_ID)

        response = await delete_invite(
            security=security, service=service, prsl_id=PRSL_ID, invite_id=invite_id
        )

        assert response.status == "deleted"
        service.delete_invite.assert_awaited_once_with(
            invite_id=invite_id, acting_as=security.auth
        )

    async def test_delete_invite_matching_admin_subgroup_succeeds(self):
        # Invites for the admin (/w/a) tier of the proposal's groups are still that
        # proposal's invites, not a mismatch.
        service = create_autospec(user_portal.UserPortalService, instance=True)
        service.get_invite.return_value = _invite_card(group_name=f"app:pht:{PRSL_ID}/w/a")
        service.delete_invite.return_value = {"status": "deleted"}

        response = await delete_invite(
            security=_pi_security(PRSL_ID),
            service=service,
            prsl_id=PRSL_ID,
            invite_id=uuid4(),
        )

        assert response.status == "deleted"


def _member(user_id: str, display_name: str) -> dict:
    """A member card as the portal returns it"""
    return {
        "portal_user_id": str(uuid4()),
        "iam_user_id": str(uuid4()),
        "preferred_username": user_id,
        "display_name": display_name,
        "email": f"{display_name.lower()}@example.org",
        "affiliation": "SKAO",
    }


def _members_service(by_group: dict[str, list[dict]], stale: bool = False):
    service = create_autospec(user_portal.UserPortalService, instance=True)

    async def list_group_members(group_name):
        return {"members": by_group.get(group_name, []), "as_of": None, "stale": stale}

    service.list_group_members.side_effect = list_group_members
    return service


class TestListMembers:
    async def test_queries_every_tier_of_the_proposal_groups(self):
        service = _members_service({})

        await list_members(security=_pi_security(PRSL_ID), service=service, prsl_id=PRSL_ID)

        requested = {c.args[0] for c in service.list_group_members.await_args_list}
        assert requested == {
            f"app:pht:{PRSL_ID}",
            f"app:pht:{PRSL_ID}/w",
            f"app:pht:{PRSL_ID}/w/a",
        }

    async def test_merges_tiers_per_person_with_highest_access(self):
        # Fixed card dicts, so the same person has the same portal ids in each tier
        pi = _member("pi-id", "Pat")
        coi = _member("coi-id", "Cory")
        reader = _member("reader-id", "Robin")
        service = _members_service(
            {
                # The PI who created the proposal is only in the admin group
                f"app:pht:{PRSL_ID}/w/a": [pi],
                f"app:pht:{PRSL_ID}/w": [coi],
                f"app:pht:{PRSL_ID}": [coi, reader],
            }
        )

        response = await list_members(
            security=_pi_security(PRSL_ID), service=service, prsl_id=PRSL_ID
        )

        access = {m.user_id: (m.has_write, m.is_admin) for m in response.members}
        assert access == {
            "pi-id": (True, True),
            "coi-id": (True, False),
            "reader-id": (False, False),
        }
        # Admins first, then writers, then readers
        assert [m.user_id for m in response.members] == ["pi-id", "coi-id", "reader-id"]
        assert response.members[0].email == "pat@example.org"
        assert response.stale is False

    async def test_member_user_id_is_the_indigo_username(self):
        member = _member("indigo-username", "Indy") | {"portal_user_id": None, "email": None}
        service = _members_service({f"app:pht:{PRSL_ID}": [member]})

        response = await list_members(
            security=_pi_security(PRSL_ID), service=service, prsl_id=PRSL_ID
        )

        # No portal-specific identifiers leak into our response
        assert response.model_dump(mode="json")["members"][0] == {
            "user_id": "indigo-username",
            "display_name": "Indy",
            "email": None,
            "affiliation": "SKAO",
            "has_write": False,
            "is_admin": False,
        }

    async def test_reports_stale_portal_data(self):
        service = _members_service({}, stale=True)

        response = await list_members(
            security=_pi_security(PRSL_ID), service=service, prsl_id=PRSL_ID
        )

        assert response.stale is True

    async def test_cannot_list_members_of_other_proposal(self):
        service = _members_service({})

        with pytest.raises(AuthFailError):
            await list_members(
                security=_pi_security(PRSL_ID), service=service, prsl_id=OTHER_PRSL_ID
            )

        service.list_group_members.assert_not_awaited()

    async def test_member_without_username_fails_loudly(self):
        # The portal excludes "disabled" accounts (no preferred_username) from its
        # external API, so a null here is a contract violation, not a member to show
        service = _members_service({f"app:pht:{PRSL_ID}": [_member(None, "Ada")]})

        with pytest.raises(UserPortalContractError):
            await list_members(security=_pi_security(PRSL_ID), service=service, prsl_id=PRSL_ID)


class TestPortalUnavailable:
    def test_is_a_bad_gateway(self, client):
        unavailable = UserPortalUnavailableError("down", HTTPStatus.SERVICE_UNAVAILABLE)
        with patch.object(user_portal, "call_user_portal", AsyncMock(side_effect=unavailable)):
            response = client.get(f"{PHT_BASE_API_URL}/users/search", params={"q": "alice"})

        assert response.status_code == HTTPStatus.BAD_GATEWAY
