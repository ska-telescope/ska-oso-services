"""
Unit tests for ska_oso_services.pht.api.user_portal
"""

from datetime import datetime, timezone
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_services.common.error_handling import NotFoundError
from ska_oso_services.pht.api.user_portal import delete_invite
from ska_oso_services.pht.service import user_portal
from ska_oso_services.pht.service.security import SecurityService

PRSL_ID = "prp-abc123"
OTHER_PRSL_ID = "prp-zzz999"
USER_ID = "a1baebc7-2d1a-4a35-ac07-478d2fc6af95"


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
        token_claims={},
        access_token="test-token",
    )
    return SecurityService(auth)


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

        response = await delete_invite(
            security=_pi_security(PRSL_ID),
            service=service,
            prsl_id=PRSL_ID,
            invite_id=uuid4(),
        )

        assert response.status == "deleted"

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
