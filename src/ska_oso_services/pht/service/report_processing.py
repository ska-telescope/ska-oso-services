
from ska_oso_services.pht.models.schemas import ProposalReportResponse

def _get_array_class(proposal) -> str:
    arrays = set()

    for obs in getattr(proposal.info, "observation_sets", []) or []:
        array_detail = getattr(obs, "array_details", None)
        if array_detail and getattr(array_detail, "array", None):
            array = array_detail.array.lower()
            if "low" in array:
                arrays.add("LOW")
            elif "mid" in array:
                arrays.add("MID")

    if "LOW" in arrays and "MID" in arrays:
        return "BOTH"
    elif "LOW" in arrays:
        return "LOW"
    elif "MID" in arrays:
        return "MID"
    return "UNKNOWN"


def join_proposals_panels_reviews_decisions(
    proposals, panels, reviews, decisions
) -> list[ProposalReportResponse]:
    """Joins all input data into output rows, handling unavailable entities."""
    rows = []

    panel_by_id = {p.panel_id: p for p in panels} if panels else {}
    decision_by_pid = {d.prsl_id: d for d in decisions} if decisions else {}

    # Index reviews by (prsl_id, reviewer_id) tuple
    review_lookup = {}
    for review in reviews or []:
        review_lookup[(review.prsl_id, review.reviewer_id)] = review

    for proposal in proposals:
        prsl_id = proposal.prsl_id
        decision = decision_by_pid.get(prsl_id)

        # Find associated panel (via assigned proposal ids)
        panel = next(
            (
                p
                for p in panel_by_id.values()
                if any(pp.prsl_id == prsl_id for pp in (p.proposals or []))
            ),
            None,
        )

        if panel and panel.reviewers:
            for reviewer in panel.reviewers:
                reviewer_id = reviewer.reviewer_id
                reviewer_status = reviewer.status
                review = review_lookup.get((prsl_id, reviewer_id))

                rows.append(
                    ProposalReportResponse(
                        prsl_id=proposal.prsl_id,
                        title=proposal.info.title,
                        science_category=proposal.info.science_category,
                        proposal_status=proposal.status,
                        proposal_type=proposal.info.proposal_type.main_type,
                        proposal_attributes=proposal.info.proposal_type.attributes
                        or [],
                        cycle=proposal.cycle,
                        array=_get_array_class(proposal),
                        panel_id=panel.panel_id,
                        assigned_proposal=(
                            "Yes"
                            if panel
                            and any(
                                pp.prsl_id == prsl_id for pp in (panel.proposals or [])
                            )
                            else "No"
                        ),
                        panel_name=panel.name,
                        reviewer_id=reviewer_id,
                        reviewer_status=reviewer_status,
                        review_status=review.status if review else None,
                        conflict=(
                            review.review_type.conflict.has_conflict
                            if review and review.review_type.conflict
                            else False
                        ),
                        review_id=review.review_id if review else None,
                        review_rank=review.review_type.rank if review else None,
                        comments=review.comments if review else None,
                        review_submitted_on=(
                            review.submitted_on.isoformat()
                            if review and review.submitted_on
                            else None
                        ),
                        decision_id=decision.prsl_id if decision else None,
                        recommendation=decision.recommendation if decision else None,
                        decision_status=decision.status if decision else None,
                        panel_rank=decision.rank if decision else None,
                        panel_score=decision.score if decision else None,
                        decision_on=(
                            decision.decided_on.isoformat()
                            if decision and decision.decided_on
                            else None
                        ),
                    )
                )
        else:
            # No panel/reviewers — fallback to proposal + decision only
            rows.append(
                ProposalReportResponse(
                    prsl_id=proposal.prsl_id,
                    title=proposal.info.title,
                    science_category=proposal.info.science_category,
                    proposal_status=proposal.status,
                    proposal_type=proposal.info.proposal_type.main_type,
                    proposal_attributes=proposal.info.proposal_type.attributes or [],
                    cycle=proposal.cycle,
                    array=_get_array_class(proposal),
                    panel_id=panel.panel_id if panel else None,
                    assigned_proposal=(
                        "Yes"
                        if panel
                        and any(pp.prsl_id == prsl_id for pp in (panel.proposals or []))
                        else "No"
                    ),
                    panel_name=panel.name if panel else None,
                    decision_id=decision.prsl_id if decision else None,
                    recommendation=decision.recommendation if decision else None,
                    decision_status=decision.status if decision else None,
                    panel_rank=decision.rank if decision else None,
                    panel_score=decision.score if decision else None,
                    decision_on=(
                        decision.decided_on.isoformat()
                        if decision and decision.decided_on
                        else None
                    ),
                )
            )

    return rows
