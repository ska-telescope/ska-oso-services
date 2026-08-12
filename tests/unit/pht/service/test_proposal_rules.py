from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pytest
from ska_aaa_authhelpers import AuthContext, AuthFailError
from ska_aaa_authhelpers.roles import Role

from ska_oso_services.pht.service.security.facts import (
    PHT_ADMIN_GROUP,
    Facts,
    get_group_name,
)
from ska_oso_services.pht.service.security.rules.proposals import ProposalRules


def mock_facts(
    *,
    is_pht_admin: bool = False,
    is_member: bool = False,
    is_pi: bool = False,
    has_write: bool = False,
    known_proposals: tuple[str, ...] = (),
) -> Mock:
    facts = Mock(spec=Facts)
    facts.auth = MagicMock(spec=AuthContext)
    facts.is_pht_admin.return_value = is_pht_admin
    facts.is_member_of.return_value = is_member
    facts.is_pi.return_value = is_pi
    facts.has_write_membership.return_value = has_write
    facts.get_all_proposals_and_panels.return_value = (
        {pid: object() for pid in known_proposals},
        {},
    )
    return facts


@pytest.mark.parametrize(
    ("facts", "prsl_ids", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=False, is_member=False),
            ("prp-1",),
            pytest.raises(AuthFailError, match="You are not a member of"),
            id="deny-when-no-membership",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_member=True),
            ("prp-1", "prp-2"),
            nullcontext(),
            id="allow-when-member-of-all",
        ),
        pytest.param(
            mock_facts(is_pht_admin=True, is_member=False),
            ("prp-1", "prp-2"),
            nullcontext(),
            id="allow-when-pht-admin",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_member=False),
            ("prp-1", "prp-2"),
            pytest.raises(AuthFailError, match="prp-2"),
            id="deny-when-not-member-of-any",
        ),
    ],
)
def test_allowed_to_view(facts, prsl_ids, expectation):

    rules = ProposalRules(facts)

    with expectation:
        rules.allowed_to_view(*prsl_ids)


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_pi=False, has_write=False, is_member=False),
            nullcontext(),
            id="allow-pht-admin",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=True, has_write=False, is_member=False),
            nullcontext(),
            id="allow-pi",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False, has_write=True, is_member=False),
            nullcontext(),
            id="allow-write-membership",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False, has_write=False, is_member=True),
            pytest.raises(AuthFailError, match="grant you edit privileges"),
            id="deny-member-without-write",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False, has_write=False, is_member=False),
            pytest.raises(AuthFailError, match="be invited"),
            id="deny-non-member",
        ),
    ],
)
def test_allowed_to_edit(facts, expectation):

    rules = ProposalRules(facts)

    with expectation:
        rules.allowed_to_edit("prp-1")


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_pi=False), nullcontext(), id="submit-allow-admin"
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=True), nullcontext(), id="submit-allow-pi"
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False),
            pytest.raises(AuthFailError, match="Principal Investigator"),
            id="submit-deny-non-pi",
        ),
    ],
)
def test_allowed_to_submit(facts, expectation):

    rules = ProposalRules(facts)

    with expectation:
        rules.allowed_to_submit("prp-1")


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_pi=False), nullcontext(), id="administer-allow-admin"
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=True), nullcontext(), id="administer-allow-pi"
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False),
            pytest.raises(AuthFailError, match="administer proposal"),
            id="administer-deny-non-pi",
        ),
    ],
)
def test_allowed_to_administer(facts, expectation):

    rules = ProposalRules(facts)

    with expectation:
        rules.allowed_to_administer("prp-1")


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_pi=False, has_write=False),
            nullcontext(),
            id="view-members-allow-admin",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=True, has_write=False),
            nullcontext(),
            id="view-members-allow-pi",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False, has_write=True),
            nullcontext(),
            id="view-members-allow-write-member",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_pi=False, has_write=False),
            pytest.raises(AuthFailError, match="cannot view the members"),
            id="view-members-deny",
        ),
    ],
)
def test_allowed_to_view_other_members(facts, expectation):

    rules = ProposalRules(facts)

    with expectation:
        rules.allowed_to_view_other_members("prp-1")


PRSL_ID = "prp-test123456789"
_AUDIENCE = "test:pht"


def _rules_from_group(group: str) -> ProposalRules:
    """Build ProposalRules with an AuthContext carrying the given group principals."""
    user_id = "test-user"
    with_subgroups = []
    subgroups = group.split("/")
    for p in range(1, len(subgroups) + 1):
        with_subgroups.append("/".join(subgroups[:p]))

    auth = AuthContext(
        user_id=user_id,
        principals=with_subgroups + [user_id],
        groups=with_subgroups,
        scopes=["pht:read", "pht:readwrite"],
        roles=[Role.ANY],
        audience=_AUDIENCE,
        token_claims={},
        access_token="",
    )
    return ProposalRules(Facts(auth))


class TestProposalRulesWithGroups:
    def test_pht_admin_group_bypasses_all_checks(self):
        rules = _rules_from_group(PHT_ADMIN_GROUP)
        rules.allowed_to_view(PRSL_ID)
        rules.allowed_to_edit(PRSL_ID)
        rules.allowed_to_submit(PRSL_ID)

    def test_pi_group_allows_view_edit_submit(self):
        rules = _rules_from_group(get_group_name(PRSL_ID, admin=True))
        rules.allowed_to_view(PRSL_ID)
        rules.allowed_to_edit(PRSL_ID)
        rules.allowed_to_submit(PRSL_ID)

    def test_write_group_allows_view_edit_not_submit(self):
        rules = _rules_from_group(get_group_name(PRSL_ID, write=True))
        rules.allowed_to_view(PRSL_ID)
        rules.allowed_to_edit(PRSL_ID)
        with pytest.raises(AuthFailError):
            rules.allowed_to_submit(PRSL_ID)

    def test_read_group_allows_view_not_edit(self):
        rules = _rules_from_group(get_group_name(PRSL_ID))
        rules.allowed_to_view(PRSL_ID)
        with pytest.raises(AuthFailError):
            rules.allowed_to_edit(PRSL_ID)

    def test_no_relevant_group_denies_all(self):
        rules = _rules_from_group("role/sci_community")
        with pytest.raises(AuthFailError):
            rules.allowed_to_view(PRSL_ID)
        with pytest.raises(AuthFailError):
            rules.allowed_to_edit(PRSL_ID)
        with pytest.raises(AuthFailError):
            rules.allowed_to_submit(PRSL_ID)

    def test_group_for_one_proposal_does_not_grant_access_to_another(self):
        rules = _rules_from_group(get_group_name(PRSL_ID, admin=True))
        with pytest.raises(AuthFailError):
            rules.allowed_to_view("prp-other1")
