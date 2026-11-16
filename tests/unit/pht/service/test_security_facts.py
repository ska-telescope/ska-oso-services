from unittest import mock

import pytest
from pydantic import ValidationError
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_services.pht.service.security import facts as facts_module
from ska_oso_services.pht.service.security.facts import (
    Facts,
    Membership,
    get_group_name,
    get_group_skuid,
)
from ska_oso_services.settings import GroupNamesConfig

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
        pytest.param("pnl-xyz999", False, False, "app:pht:pnl-xyz999", id="panel-group"),
        pytest.param("pnl-xyz999", True, False, "app:pht:pnl-xyz999/w/a", id="chair-group"),
    ],
)
def test_get_group_name(skuid, admin, write, expected):
    assert get_group_name(skuid, admin=admin, write=write) == expected


@pytest.mark.parametrize(
    ("group_name", "expected"),
    [
        pytest.param("app:pht:prp-abc123", "prp-abc123", id="base-group"),
        pytest.param("app:pht:prp-abc123/w", "prp-abc123", id="write-group"),
        pytest.param("app:pht:prp-abc123/w/a", "prp-abc123", id="admin-group"),
        pytest.param("app:pht:pnl-xyz999/w/a", "pnl-xyz999", id="panel-admin-group"),
    ],
)
def test_get_group_skuid(group_name, expected):
    assert get_group_skuid(group_name) == expected


@pytest.mark.parametrize(
    "group_name",
    [
        pytest.param("app:pht:ops_proposal_admin", id="not-a-skuid-group"),
        pytest.param("app:other:prp-abc123/w", id="non-pht-group"),
        pytest.param("not-a-group-at-all", id="malformed-group"),
        pytest.param(" app:pht:prp-abc123/w/a ", id="untrimmed-whitespace"),
    ],
)
def test_get_group_skuid_raises_on_unrecognised_group_name(group_name):
    with pytest.raises(ValueError, match="Not a valid PHT group name"):
        get_group_skuid(group_name)


def test_get_group_skuid_does_not_match_a_similarly_prefixed_skuid():
    # "prp-abc123" must not be mistaken for a match of "prp-abc1234".
    assert get_group_skuid("app:pht:prp-abc1234/w/a") != "prp-abc123"


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
                Membership("pnl-xyz999", True, False),
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
                # Panels have no write tier, so their /w (the chair group's parent) is ignored
                "pnl-xyz999": Membership("pnl-xyz999", False, False),
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


def test_panels_have_no_write_group():
    with pytest.raises(ValueError, match="no such group"):
        get_group_name("pnl-xyz999", write=True)


@pytest.fixture
def renamed_groups():
    names = GroupNamesConfig(
        base="ska:{skuid}", coi_suffix="/coi", pi_suffix="/coi/pi", chair_suffix="/chair"
    )
    with mock.patch.object(facts_module, "get_settings") as get_settings:
        get_settings.return_value.groups = names
        yield


@pytest.mark.usefixtures("renamed_groups")
class TestConfiguredGroupNames:
    @pytest.mark.parametrize(
        ("skuid", "admin", "write", "expected"),
        [
            pytest.param("prp-abc123", False, False, "ska:prp-abc123", id="base-group"),
            pytest.param("prp-abc123", False, True, "ska:prp-abc123/coi", id="coi-group"),
            pytest.param("prp-abc123", True, False, "ska:prp-abc123/coi/pi", id="pi-group"),
            pytest.param("pnl-xyz999", True, False, "ska:pnl-xyz999/chair", id="chair-group"),
        ],
    )
    def test_names_groups(self, skuid, admin, write, expected):
        assert get_group_name(skuid, admin=admin, write=write) == expected

    def test_parses_groups(self):
        auth = make_auth_context(
            "ska:prp-abc123/coi",
            "ska:prp-def456/coi/pi",
            "ska:pnl-xyz999/chair",
            "app:pht:prp-ghi789/w",  # the default names no longer count
            "ska:pnl-uvw111/coi",  # a proposal tier on a panel
        )

        proposals, panels = Facts(auth).get_all_proposals_and_panels()

        assert proposals == {
            "prp-abc123": Membership("prp-abc123", False, True),
            "prp-def456": Membership("prp-def456", True, True),
        }
        assert panels == {"pnl-xyz999": Membership("pnl-xyz999", True, False)}


class TestGroupNamesConfig:
    def test_base_needs_the_skuid_placeholder(self):
        with pytest.raises(ValidationError, match="skuid"):
            GroupNamesConfig(base="app:pht")

    @pytest.mark.parametrize(
        "field",
        ["coi_suffix", "pi_suffix", "chair_suffix"],
    )
    @pytest.mark.parametrize(
        "suffix",
        [
            pytest.param("w", id="not-a-subgroup"),  # app:pht:prp-123w reads as prp-123w
            pytest.param("-pi", id="sibling-group"),
            pytest.param("/", id="empty-name"),
            pytest.param("/w/", id="trailing-slash"),
            pytest.param("/w//a", id="empty-segment"),
        ],
    )
    def test_suffixes_must_be_subgroups(self, field, suffix):
        with pytest.raises(ValidationError, match="pattern"):
            GroupNamesConfig(**{field: suffix})

    @pytest.mark.parametrize(
        "pi_suffix",
        [
            pytest.param("/w", id="same-as-coi"),
            pytest.param("/a", id="sibling-of-coi"),
            pytest.param("/wa", id="prefixed-but-not-under-coi"),
        ],
    )
    def test_pi_suffix_must_be_under_the_coi_suffix(self, pi_suffix):
        with pytest.raises(ValidationError, match="subgroup of the Co-Investigator"):
            GroupNamesConfig(coi_suffix="/w", pi_suffix=pi_suffix)

    def test_accepts_renamed_hierarchical_suffixes(self):
        names = GroupNamesConfig(coi_suffix="/coi", pi_suffix="/coi/pi", chair_suffix="/chair")

        assert names.pi_suffix == "/coi/pi"

    def test_reads_the_environment(self, monkeypatch):
        monkeypatch.setenv("PHT_GROUP_CHAIR_SUFFIX", "/chair")

        assert GroupNamesConfig().chair_suffix == "/chair"
