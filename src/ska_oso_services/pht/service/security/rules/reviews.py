from ska_oso_pdm import PanelReview

from ._shared import BaseRules, RuleResult, auth_rule


class ReviewRules(BaseRules):
    """
    Rules for individual PanelReview records.

    Note: whether a review is a science or technical review is now an attribute
    of the review itself (``review.review_type.kind``, set based on the panel's
    assignment of the proposal), not a global property of the reviewing user.
    There is no longer a distinct "science reviewer" / "technical reviewer" role
    to check here - access is governed by panel membership (see PanelRules) and,
    for editing, by whether the user is the specific reviewer the review was
    assigned to.
    """

    @auth_rule
    def allowed_to_edit(self, review: PanelReview) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can edit any review")
        if review.reviewer_id == self.facts.auth.user_id:
            return RuleResult(True, "User is the reviewer who authored this review")
        return RuleResult(False, "Only the reviewer or a PHT admin can edit this review")

    @auth_rule
    def allowed_to_view(self, *review_ids: str) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view reviews")
        return RuleResult(False, f"User cannot view reviews: {sorted(review_ids)}")
