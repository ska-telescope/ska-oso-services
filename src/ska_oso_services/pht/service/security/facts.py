import re
from collections import defaultdict
from enum import Enum
from functools import cache
from typing import Generator, Literal, NamedTuple

from ska_aaa_authhelpers import AuthContext, Role
from ska_ser_skuid import EntityType, ShortSkuid

from ska_oso_services.settings import get_settings

PHT_ADMIN_GROUP = "app:pht:ops_proposal_admin"

ProposalID = ShortSkuid[Literal[EntityType.PRP]]
PanelID = ShortSkuid[Literal[EntityType.PNL]]


class PhtScope(str, Enum):
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"


# The entity types that have access groups
GROUP_ENTITY_TYPES = (EntityType.PRP, EntityType.PNL)


def _entity_type(skuid: str) -> EntityType:
    # A SKUID's prefix is its entity type
    return EntityType(skuid.partition("-")[0])


def get_group_name(skuid: ShortSkuid, admin=False, write=False) -> str:
    """
    The name of a proposal's or panel's group: its members' by default, or with admin
    its PIs' (for a proposal) or chairs' (for a panel), or with write its
    Co-Investigators' (proposals only).
    """
    names = get_settings().groups
    base = names.base.format(skuid=skuid)
    match _entity_type(skuid), admin, write:
        case EntityType.PRP, True, _:
            return base + names.pi_suffix
        case EntityType.PRP, False, True:
            return base + names.coi_suffix
        case EntityType.PNL, True, False:
            return base + names.chair_suffix
        case _, False, False:
            return base
        case _:
            raise ValueError(f"{skuid} has no such group (admin={admin}, write={write})")


class Membership(NamedTuple):
    skuid: ShortSkuid
    is_admin: bool
    has_write: bool


@cache
def _group_regex(base: str, suffixes: frozenset[str]) -> re.Pattern[str]:
    before, after = base.split("{skuid}")
    entity_types = "|".join(GROUP_ENTITY_TYPES)
    return re.compile(
        f"^{re.escape(before)}"
        f"(?P<skuid>(?:{entity_types})-[a-hj-kmnp-tv-z0-9]+)"
        f"{re.escape(after)}"
        f"(?P<suffix>{'|'.join(map(re.escape, suffixes))})?$"
    )


def _parse_group_name(group_name: str) -> Membership | None:
    names = get_settings().groups
    suffixes = frozenset({names.coi_suffix, names.pi_suffix, names.chair_suffix})
    if not (match := _group_regex(names.base, suffixes).match(group_name)):
        return None
    skuid, suffix = match.group("skuid"), match.group("suffix")
    # (is_admin, has_write) of each tier the entity has; None is the members group
    match _entity_type(skuid):
        case EntityType.PRP:
            tiers = {
                None: (False, False),
                names.coi_suffix: (False, True),
                names.pi_suffix: (True, True),
            }
        case EntityType.PNL:
            tiers = {None: (False, False), names.chair_suffix: (True, False)}
        case _:
            return None
    if suffix not in tiers:
        return None  # e.g. a proposal's suffix on a panel
    return Membership(skuid, *tiers[suffix])


def get_group_skuid(group_name: str) -> str:
    """Extract the proposal/panel skuid a group belongs to, whichever tier it is."""
    if membership := _parse_group_name(group_name):
        return membership.skuid
    else:
        raise ValueError(f"Not a valid PHT group name: {group_name!r}")


class ProposalsAndPanels(NamedTuple):
    proposals: dict[ProposalID, Membership]
    panels: dict[PanelID, Membership]


class Facts:
    auth: AuthContext

    def __init__(self, auth: AuthContext) -> None:
        self.auth = auth

    def _iter_pht_groups(self) -> Generator[Membership, None, None]:
        for grp in self.auth.principals:
            if membership := _parse_group_name(grp.strip()):
                yield membership

    def get_all_proposals_and_panels(
        self,
    ) -> ProposalsAndPanels:
        merged: defaultdict[ShortSkuid, tuple[bool, bool]] = defaultdict(lambda: (False, False))
        for membership in self._iter_pht_groups():
            skuid = membership.skuid
            existing_is_admin, existing_has_write = merged[skuid]
            merged[skuid] = (
                membership.is_admin or existing_is_admin,
                membership.has_write or existing_has_write,
            )

        proposals, panels = {}, {}
        for skuid, (is_admin, has_write) in merged.items():
            membership = Membership(skuid=skuid, is_admin=is_admin, has_write=has_write)
            match _entity_type(skuid):
                case EntityType.PRP:
                    proposals[skuid] = membership
                case EntityType.PNL:
                    panels[skuid] = membership
        return ProposalsAndPanels(proposals, panels)

    def is_me(self, user_id: str) -> bool:
        return self.auth.user_id == user_id

    def is_pht_admin(self) -> bool:
        # Could Role.SCI_COMMUNITY folks ever
        # be added to the PHT admin group?
        Role.INTERNAL  # Prevent unused import
        # if Role.INTERNAL not in self.auth.roles:
        #     return False
        return PHT_ADMIN_GROUP in self.auth.principals

    def is_member_of(self, skuid: PanelID | ProposalID) -> bool:
        return get_group_name(skuid) in self.auth.principals

    def is_pi(self, skuid: ProposalID) -> bool:
        return self._is_admin_of(skuid)

    def is_chair(self, skuid: PanelID) -> bool:
        return self._is_admin_of(skuid)

    def _is_admin_of(self, skuid: ProposalID | PanelID) -> bool:
        return get_group_name(skuid, admin=True) in self.auth.principals

    def has_write_membership(self, skuid: ProposalID) -> bool:
        # PIs can write too, whether or not their group is a subgroup of the CoIs'
        return get_group_name(skuid, write=True) in self.auth.principals or self.is_pi(skuid)
