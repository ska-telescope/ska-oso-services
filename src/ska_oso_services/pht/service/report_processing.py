from itertools import chain

from ska_oso_services.pht.models.schemas import ProposalReportResponse


def _get_array_class(proposal) -> str:
    arrays = set()

    for obs in getattr(proposal.observation_info, "observation_sets", []) or []:
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

        if panel and (panel.sci_reviewers or panel.tech_reviewers):
            seen: set[str] = set()
            for reviewer in chain(
                panel.sci_reviewers or [], panel.tech_reviewers or []
            ):
                rid = reviewer.reviewer_id
                if rid in seen:
                    continue
                seen.add(rid)

                reviewer_id = rid
                reviewer_status = reviewer.status
                review = review_lookup.get((prsl_id, reviewer_id))

                rows.append(
                    ProposalReportResponse(
                        prsl_id=proposal.prsl_id,
                        title=proposal.proposal_info.title,
                        science_category=proposal.proposal_info.science_category,
                        proposal_status=proposal.status,
                        proposal_type=proposal.proposal_info.proposal_type.main_type,
                        proposal_attributes=proposal.proposal_info.proposal_type.attributes  # noqa: E501
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
                        review_type=review.review_type.kind if review else None,
                        review_status=review.status if review else None,
                        conflict=(
                            review.review_type.conflict.has_conflict
                            if review and review.review_type.kind == "Science Review"
                            else False
                        ),
                        review_id=review.review_id if review else None,
                        review_rank=(
                            getattr(getattr(review, "review_type", None), "rank", None)
                            if review
                            else None
                        ),
                        comments=review.comments if review else None,
                        decision_id=decision.prsl_id if decision else None,
                        recommendation=decision.recommendation if decision else None,
                        decision_status=decision.status if decision else None,
                        panel_rank=decision.rank if decision else None,
                        panel_score=decision.score if decision else None,
                    )
                )
        else:
            # No panel/reviewers — fallback to proposal + decision only
            rows.append(
                ProposalReportResponse(
                    prsl_id=proposal.prsl_id,
                    title=proposal.proposal_info.title,
                    science_category=proposal.proposal_info.science_category,
                    proposal_status=proposal.status,
                    proposal_type=proposal.proposal_info.proposal_type.main_type,
                    proposal_attributes=proposal.proposal_info.proposal_type.attributes
                    or [],
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
                )
            )

    return rows
