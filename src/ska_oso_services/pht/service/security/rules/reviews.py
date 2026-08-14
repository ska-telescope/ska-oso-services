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
    def allowed_to_create(self, review: PanelReview) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can create any review")
        if self.facts.is_me(review.reviewer_id) and self.facts.is_member_of(review.panel_id):
            return RuleResult(
                True, "User is allowed to write a review for the panel they are a member of"
            )
        return RuleResult(
            False,
            f"Only members of the panel {review.panel_id} can create reviews for that panel.",
        )

    @auth_rule
    def allowed_to_edit(self, review: PanelReview) -> RuleResult:
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can edit any review")
        elif self.facts.is_me(review.reviewer_id):
            return RuleResult(True, "User is the reviewer who authored this review")
        return RuleResult(False, "Only the reviewer or a PHT admin can edit this review")

    @auth_rule
    def allowed_to_view(self, review: PanelReview) -> RuleResult:
        """
        Allows viewing of an individual review record.
        The chair of the panel, the PHT admin, and the author of the review are allowed.
        """
        if self.facts.is_pht_admin():
            return RuleResult(True, "PHT admin can view any review")
        elif self.facts.is_chair(review.panel_id):
            return RuleResult(True, f"Chair of panel {review.panel_id} can view the review")
        elif self.facts.is_me(review.reviewer_id):
            return RuleResult(True, "Review author can view their review")
        else:
            return RuleResult(
                False,
                f"Only the author, panel chair, or PHT admin can view review {review.review_id}",
            )
