import pytest
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_services.pht.service.security.facts import Facts, Membership, get_group_name

USER_ID = "a1baebc7-2d1a-4a35-ac07-478d2fc6af95"


def make_auth_context(
    *groups: str,
) -> AuthContext:
    return AuthContext(
        user_id=USER_ID,
        principals=frozenset(groups + (USER_ID,)),
        roles=frozenset({Role.ANY}),
        groups=frozenset(groups),
        scopes=frozenset(("pht:readwrite",)),
        audience="test:pht",
        token_claims={},
        access_token="test-token",
    )


@pytest.mark.parametrize(
    ("skuid", "admin", "write", "expected"),
    [
        pytest.param("prp-abc123", False, False, "app:pht:prp-abc123", id="base-group"),
        pytest.param("prp-abc123", False, True, "app:pht:prp-abc123/w", id="write-group"),
        pytest.param("prp-abc123", True, False, "app:pht:prp-abc123/w/a", id="admin-group"),
    ],
)
def test_get_group_name(skuid, admin, write, expected):
    assert get_group_name(skuid, admin=admin, write=write) == expected


@pytest.mark.parametrize(
    ("auth", "expected"),
    [
        pytest.param(
            make_auth_context(
                "role/internal",
                "app:pht:prp-abc123",
                " app:pht:prp-abc123/w ",
                "app:pht:pnl-xyz999/w/a",
                "app:pht:ops_proposal_admin",
            ),
            [
                Membership("prp-abc123", False, False),
                Membership("prp-abc123", False, True),
                Membership("pnl-xyz999", True, True),
            ],
            id="parse-base-write-admin-subgroup",
        ),
        pytest.param(
            make_auth_context("app:other:prp-abc123/w", "role/sci_community"),
            [],
            id="ignore-non-pht-groups",
        ),
    ],
)
def test_iter_pht_groups(auth, expected):
    facts = Facts(auth)
    actual = sorted(
        facts._iter_pht_groups(), key=lambda item: (item.skuid, item.is_admin, item.has_write)
    )
    expected_sorted = sorted(
        expected, key=lambda item: (item.skuid, item.is_admin, item.has_write)
    )
    assert actual == expected_sorted


@pytest.mark.parametrize(
    ("auth", "expected_proposals", "expected_panels"),
    [
        pytest.param(
            make_auth_context(
                "role/sci_community",
                "someother:group",
                "app:pht:prp-abc123",
                "app:pht:prp-abc123/w",
                "app:pht:prp-abc123/w/a",
                "app:pht:pnl-xyz999",
                "app:pht:pnl-xyz999/w",
            ),
            {
                "prp-abc123": Membership("prp-abc123", True, True),
            },
            {
                "pnl-xyz999": Membership("pnl-xyz999", False, True),
            },
            id="collapse-memberships-per-skuid",
        ),
    ],
)
def test_get_all_proposals_and_panels_collapses_memberships(
    auth, expected_proposals, expected_panels
):
    facts = Facts(auth)
    proposals, panels = facts.get_all_proposals_and_panels()
    assert proposals == expected_proposals
    assert panels == expected_panels


@pytest.mark.parametrize(
    (
        "auth",
        "skuid",
        "expected_is_member",
        "expected_is_pi",
        "expected_has_write",
    ),
    [
        pytest.param(
            make_auth_context("app:pht:prp-abc123"),
            "prp-abc123",
            True,
            False,
            False,
            id="base-membership-only",
        ),
        pytest.param(
            make_auth_context("app:pht:prp-abc123", "app:pht:prp-abc123/w"),
            "prp-abc123",
            True,
            False,
            True,
            id="write-membership",
        ),
        pytest.param(
            make_auth_context(
                "app:pht:prp-abc123", "app:pht:prp-abc123/w", "app:pht:prp-abc123/w/a"
            ),
            "prp-abc123",
            True,
            True,
            True,
            id="admin-membership",
        ),
    ],
)
def test_membership_checks(auth, skuid, expected_is_member, expected_is_pi, expected_has_write):
    facts = Facts(auth)
    assert facts.is_member_of(skuid) is expected_is_member
    assert facts.is_pi(skuid) is expected_is_pi
    assert facts.has_write_membership(skuid) is expected_has_write


@pytest.mark.parametrize(
    ("auth", "expected"),
    [
        pytest.param(make_auth_context("app:pht:ops_proposal_admin"), True, id="is-admin"),
        pytest.param(make_auth_context("app:pht:prp-abc123"), False, id="not-admin"),
    ],
)
def test_is_pht_admin(auth, expected):
    assert Facts(auth).is_pht_admin() is expected
