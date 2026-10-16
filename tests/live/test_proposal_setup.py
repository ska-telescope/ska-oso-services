"""
Live end-to-end check of setting up a new proposal through our API: POST /prsls/create
with a real Indigo user token, creating real groups in the staging User Portal with our
client-credentials grant. The ODA is mocked. The groups are deleted afterwards.

Skipped unless USER_PORTAL_* (including USER_PORTAL_CLIENT_SECRET) are configured. The
PI is the INDIGO_TEST_USERNAME user.
Run via: uv run --env-file .env pytest tests/live -m live
"""

import asyncio
from http import HTTPStatus
from unittest import mock
from urllib.parse import quote

import pytest
from ska_db_oda.repository.domain import ODANotFound
from ska_ser_skuid import EntityType, mint_skuid

from ska_oso_services.common.error_handling import NotFoundError
from ska_oso_services.pht.service.security.facts import get_group_name
from ska_oso_services.pht.service.user_portal import UserPortalService
from ska_oso_services.settings import get_settings
from tests.live.conftest import unverified_claims
from tests.unit.util import TestDataFactory

pytestmark = pytest.mark.live


def _proposal_groups(prsl_id: str) -> tuple[str, str, str]:
    """(base, write, admin) group names, as the app creates them."""
    return (
        get_group_name(prsl_id),
        get_group_name(prsl_id, write=True),
        get_group_name(prsl_id, admin=True),
    )


async def _delete_group(portal: UserPortalService, group_name: str, owner_sub: str) -> None:
    # The app never deletes groups, so the service has no method for it. Only the
    # group's owner may delete it, identified (like all portal writes) by INDIGO sub.
    # TODO: send the owner's username once the portal accepts it in X-Acting-User
    await portal._call(  # pylint: disable=protected-access
        method="DELETE",
        url=f"{portal.base_url}/api/external/v1/groups/{quote(group_name, safe='')}",
        extra_headers={"X-Acting-User": owner_sub},
    )


def _member_subs(portal: UserPortalService, group_name: str) -> set[str]:
    # TODO: compare on ProposalMember.user_id once the portal reports a username for
    # every member. Today preferred_username is null for an account with no portal
    # record, such as our INDIGO-only test user, so match on the INDIGO account id.
    payload = asyncio.run(portal.list_group_members(group_name))
    return {member["iam_user_id"] for member in payload["members"]}


@pytest.fixture
def pi_sub(indigo_token) -> str:
    # The INDIGO account id, which the portal records as the owner of the groups
    return unverified_claims(indigo_token)["sub"]


@pytest.fixture
def new_prsl_id(user_portal, pi_sub):
    """A fresh proposal ID whose User Portal groups are deleted after the test."""
    prsl_id = mint_skuid(EntityType.PRP)
    yield prsl_id
    # Smallest tier first, as the PI who created (and so owns) them
    for group_name in reversed(_proposal_groups(prsl_id)):
        try:
            asyncio.run(_delete_group(user_portal, group_name, owner_sub=pi_sub))
        except NotFoundError:
            pass


def test_create_proposal_sets_up_portal_groups(
    live_client, indigo_token, user_portal, pi_sub, new_prsl_id
):
    base_group, write_group, admin_group = _proposal_groups(new_prsl_id)
    proposal = TestDataFactory.proposal(prsl_id=new_prsl_id)

    with mock.patch("ska_oso_services.pht.api.prsls.oda.uow") as mock_uow:
        uow = mock_uow.return_value.__enter__.return_value
        uow.prsls.get.side_effect = ODANotFound()
        uow.prsls.add.side_effect = lambda prsl, _user_id: prsl

        response = live_client.post(
            # The app's own prefix, which may come from .env rather than the test defaults
            f"{get_settings().api_path_prefix}/pht/prsls/create",
            content=proposal.model_dump_json(),
            headers={
                "Authorization": f"Bearer {indigo_token}",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["prsl_id"] == new_prsl_id

    # The PI is the only member of the admin tier...
    assert _member_subs(user_portal, admin_group) == {pi_sub}

    # ...and so of the tiers above it (NotFoundError if they don't exist), because
    # INDIGO adds a subgroup's members to its parent groups too
    assert _member_subs(user_portal, write_group) == {pi_sub}
    assert _member_subs(user_portal, base_group) == {pi_sub}
