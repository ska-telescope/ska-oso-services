"""
Live checks against the staging User Portal, using our real client-credentials grant.

Read-only. The portal's external API only knows the groups it created itself, so
listing members of a group is covered by test_proposal_setup instead.
Skipped unless USER_PORTAL_* (including USER_PORTAL_CLIENT_SECRET) are configured.
Run via: uv run --env-file .env pytest tests/live -m live
"""

import pytest
from ska_ser_skuid import EntityType, mint_skuid

from ska_oso_services.common.error_handling import NotFoundError
from ska_oso_services.pht.models.invitations import UserSearchResponse
from ska_oso_services.pht.service.user_portal import get_token_provider, parse_portal_response
from ska_oso_services.settings import get_settings
from tests.live.conftest import unverified_claims

pytestmark = pytest.mark.live


async def test_token_has_portal_audience_and_scopes(user_portal):
    # If this fails, the portal can't accept our token: check the Indigo client's
    # allowed scopes/audience before looking at the other tests
    portal = get_settings().userportal
    claims = unverified_claims(await get_token_provider().get_token())

    audiences = {claims["aud"]} if isinstance(claims["aud"], str) else set(claims["aud"])
    assert portal.token_audience in audiences
    assert set(portal.token_scope.split()) <= set(claims.get("scope", "").split())


async def test_unknown_group_is_not_found(user_portal):
    with pytest.raises(NotFoundError):
        await user_portal.list_group_members(f"app:pht:{mint_skuid(EntityType.PRP)}")


async def test_search_results_match_our_contract(user_portal):
    # Search matches on names and email addresses, so this only checks that whatever
    # comes back is something we accept (e.g. every result has a user_id)
    parse_portal_response(UserSearchResponse, await user_portal.search_users("astronomer", 25))
