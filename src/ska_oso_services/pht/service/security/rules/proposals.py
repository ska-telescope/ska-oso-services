from typing import Literal, TypeAlias

from ska_ser_skuid import EntityType, ShortSkuid

from ._shared import BaseRules, RuleResult, auth_rule

ProposalID: TypeAlias = ShortSkuid[Literal[EntityType.PRP]]

# These rules are based on @Adam's draft from
# https://docs.google.com/document/d/1pHgDLu09dd7J81iwGi1sWx9jBJhWLZt8p8DllRCq760/edit?tab=t.0
# | Action                  | PI | CoI (edit) | CoI (view) |
# | :---------------------- | :- | :--------- | :--------- |
# | View Proposal           | ✅ | ✅         | ✅         |
# | Edit Proposal           | ✅ | ✅         | ❌         |
# | Submit Proposal         | ✅ | ❌         | ❌         |
# | Delete Proposal         | ❌ | ❌         | ❌         |
# | Add/Remove Co-Is        | ✅ | ❌         | ❌         |
# | View proposal members   | ✅ | ✅         | ❌         |
# | Manage Proposal members | ✅ | ❌         | ❌         |


class ProposalRules(BaseRules):
    @auth_rule
    def allowed_to_view(self, *prsl_ids: ProposalID):
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view any proposal")
        if all(self.facts.is_member_of(pid) for pid in prsl_ids):
            return RuleResult(True, f"You are a member of {prsl_ids}")
        proposals, _ = self.facts.get_all_proposals_and_panels()
        unauthorised = set(prsl_ids).difference(proposals)
        return RuleResult(False, f"You are not a member of {sorted(unauthorised)}")

    @auth_rule
    def allowed_to_edit(self, prsl_id: ProposalID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can edit any proposal")
        elif self.facts.is_pi(prsl_id):
            return RuleResult(True, f"User is PI of {prsl_id}")
        elif self.facts.has_write_membership(prsl_id):
            return RuleResult(True, f"User is a Co-I with edit privileges on {prsl_id}")
        else:
            if self.facts.is_member_of(prsl_id):
                return RuleResult(False, f"Ask the PI to grant you edit privileges on {prsl_id}")
            else:
                return RuleResult(False, f"Ask the PI to be invited to {prsl_id}")

    @auth_rule
    def allowed_to_submit(self, prsl_id: ProposalID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can submit any proposal")
        elif self.facts.is_pi(prsl_id):
            return RuleResult(True, f"User is PI of {prsl_id}")
        return RuleResult(
            False, f"You must be a Principal Investigator to submit proposal {prsl_id}"
        )

    @auth_rule
    def allowed_to_administer(self, prsl_id: ProposalID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT global admin can admin any proposal")
        if self.facts.is_pi(prsl_id):
            return RuleResult(True, f"PI of {prsl_id} can adminster their proposal")
        return RuleResult(
            False, f"You must be Principal Investigator to administer proposal {prsl_id}"
        )

    @auth_rule
    def allowed_to_view_other_members(self, prsl_id: ProposalID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view all proposal members")
        elif self.facts.is_pi(prsl_id):
            return RuleResult(True, f"PI of {prsl_id} can view members.")
        elif self.facts.has_write_membership(prsl_id):
            return RuleResult(True, f"Co-I  with write privileges can view members of {prsl_id}")
        else:
            return RuleResult(False, f"You cannot view the members of {prsl_id}.")
