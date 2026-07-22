from typing import Literal, TypeAlias, cast

from ska_ser_skuid import EntityType, ShortSkuid

from ._shared import BaseRules, RuleResult, auth_rule

ProposalID: TypeAlias = ShortSkuid[Literal[EntityType.PRP]]


class ReviewRules(BaseRules):
    @auth_rule
    def allowed_to_admin_review(self, prsl_id: ProposalID | str) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can create reviews")
        return RuleResult(False, "Only PHT admin can create reviews")

    @auth_rule
    def allowed_to_edit_technical_review(self) -> RuleResult:
        if self.facts.is_technical_reviewer():
            return RuleResult(True, "User is a technical reviewer")
        return RuleResult(False, "Only technical reviewers can edit technical reviews")

    @auth_rule
    def allowed_to_view_technical_review(self) -> RuleResult:
        return RuleResult(True, "All roles can view technical reviews")

    @auth_rule
    def allowed_to_edit_science_review(self) -> RuleResult:
        if self.facts.is_science_reviewer():
            return RuleResult(True, "User is a science reviewer")
        return RuleResult(False, "Only science reviewers can edit science reviews")

    @auth_rule
    def allowed_to_view_science_review(self, prsl_id: ProposalID | str) -> RuleResult:
        normalized_id = cast(ProposalID, prsl_id)
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view science reviews")
        if self.facts.is_review_chair():
            return RuleResult(True, "Review chair can view science reviews")
        if self.facts.is_member_of(normalized_id):
            return RuleResult(True, f"User is member of {prsl_id} and can view science reviews")
        if self.facts.is_science_reviewer():
            return RuleResult(True, "Science reviewer can view science reviews")
        return RuleResult(False, "User cannot view science reviews for this proposal")

    @auth_rule
    def allowed_to_submit_review(self) -> RuleResult:
        if self.facts.is_science_reviewer() or self.facts.is_technical_reviewer():
            return RuleResult(True, "Reviewer can submit review")
        return RuleResult(False, "Only reviewers can submit reviews")

    @auth_rule
    def allowed_to_view(self, *review_ids: str) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view reviews")
        return RuleResult(False, f"User cannot view reviews: {sorted(review_ids)}")
