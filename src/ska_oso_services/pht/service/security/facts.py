import re
from collections import defaultdict
from enum import Enum
from typing import Generator, Literal, NamedTuple

from ska_aaa_authhelpers import AuthContext, Role
from ska_ser_skuid import EntityType, ShortSkuid

PHT_ADMIN_GROUP = "app:pht:ops_proposal_admin"

ProposalID = ShortSkuid[Literal[EntityType.PRP]]
PanelID = ShortSkuid[Literal[EntityType.PNL]]


class PhtScope(str, Enum):
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"


def get_group_name(skuid: ShortSkuid, admin=False, write=False) -> str:
    if admin:
        return f"app:pht:{skuid}/w/a"
    elif write:
        return f"app:pht:{skuid}/w"
    else:
        return f"app:pht:{skuid}"


class Membership(NamedTuple):
    skuid: ShortSkuid
    is_admin: bool
    has_write: bool


class ProposalsAndPanels(NamedTuple):
    proposals: dict[ProposalID, Membership]
    panels: dict[PanelID, Membership]


class Facts:
    auth: AuthContext

    _group_regex = re.compile(
        r"^app:pht:"
        f"(?P<skuid>(?:{EntityType.PRP}|{EntityType.PNL})-[a-z1-9]+)"
        r"(?P<write>/w(?P<admin>/a)?)?$"
    )

    def __init__(self, auth: AuthContext) -> None:
        self.auth = auth

    def _iter_pht_groups(self) -> Generator[Membership, None, None]:
        for grp in self.auth.principals:
            if match := self._group_regex.match(grp.strip()):
                skuid = match.group("skuid")
                has_write = bool(match.group("write"))
                is_admin = bool(match.group("admin"))
                yield Membership(skuid, is_admin, has_write)

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
            if skuid.startswith(EntityType.PRP):
                proposals[skuid] = membership
            elif skuid.startswith(EntityType.PNL):
                panels[skuid] = membership
            else:
                raise ValueError("Something is wrong with _group_regex")
        return ProposalsAndPanels(proposals, panels)

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
        # Because the groups are hierarchical, members of the admin (/w/a) group will
        # automatically be in the write (/w) group by definition.
        return get_group_name(skuid, write=True) in self.auth.principals
