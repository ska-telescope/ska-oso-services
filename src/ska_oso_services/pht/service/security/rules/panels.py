from typing import Literal, TypeAlias

from ska_ser_skuid import EntityType, ShortSkuid

from ._shared import BaseRules, RuleResult, auth_rule

PanelID: TypeAlias = ShortSkuid[Literal[EntityType.PNL]]


class PanelRules(BaseRules):
    @auth_rule
    def allowed_to_view(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view any panel")
        if self.facts.is_member_of(pnl_id):
            return RuleResult(True, f"User is a member of panel {pnl_id}")
        return RuleResult(False, f"You are not a member of panel {pnl_id}")

    @auth_rule
    def allowed_to_change_members(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can change members of any panel")
        if self.facts.is_chair(pnl_id):
            return RuleResult(True, f"Chair of panel {pnl_id} can change panel members")
        return RuleResult(
            False, f"Only the chair of {pnl_id} or PHT admin can change panel members"
        )

    @auth_rule
    def allowed_to_administer(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can administer any panel")
        return RuleResult(False, f"Only PHT admin can administer panel {pnl_id}")

    # ---- Panel decision rules ----

    @auth_rule
    def allowed_to_view_decision(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view any panel decision")
        if self.facts.is_member_of(pnl_id):
            return RuleResult(True, f"Panel member can view decisions for panel {pnl_id}")
        return RuleResult(False, f"You are not a member of panel {pnl_id}")

    @auth_rule
    def allowed_to_edit_decision(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can edit any panel decision")
        if self.facts.is_chair(pnl_id):
            return RuleResult(True, f"Chair of panel {pnl_id} can edit panel decisions")
        return RuleResult(False, f"Only the chair of {pnl_id} or PHT admin can edit decisions")

    @auth_rule
    def allowed_to_submit_decision(self, pnl_id: PanelID) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can submit any panel decision")
        if self.facts.is_chair(pnl_id):
            return RuleResult(True, f"Chair of panel {pnl_id} can submit the panel decision")
        return RuleResult(
            False, f"Only the chair of {pnl_id} or PHT admin can submit a panel decision"
        )
