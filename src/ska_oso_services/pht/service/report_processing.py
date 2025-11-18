from collections import defaultdict
from typing import Optional

from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.utils.ms_graph import get_pi_office_location


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
    """Join proposals, panels, reviews, decisions at review_id-level
    (science/technical).
    Else:
        Fall back to proposal - decision when no reviews exist.
    Note: this inclludes all proposals statuses.
    """
    rows: list[ProposalReportResponse] = []

    # ---- Proposal --> panel ----
    proposal_to_panel = {}
    for p in panels or []:
        for pp in p.proposals or []:
            proposal_to_panel[pp.prsl_id] = p

    # ---- Index decisions by proposal ----
    decision_by_pid = {d.prsl_id: d for d in (decisions or [])}

    # ---- PI office location per proposal ----
    pi_location_by_prsl: dict[str, Optional[str]] = {}

    # ---- Index reviews by proposal ----
    reviews_by_prsl: dict[str, list] = defaultdict(list)
    for r in reviews or []:
        reviews_by_prsl[r.prsl_id].append(r)

    reviewer_status_lookup: dict[tuple[str, str, str], str] = {}
    for p in panels or []:
        for rv in p.sci_reviewers or []:
            reviewer_status_lookup[(p.panel_id, rv.reviewer_id, "Science Review")] = (
                rv.status
            )
        for rv in p.tech_reviewers or []:
            reviewer_status_lookup[(p.panel_id, rv.reviewer_id, "Technical Review")] = (
                rv.status
            )

    for proposal in proposals or []:
        prsl_id = proposal.prsl_id
        decision = decision_by_pid.get(prsl_id)

        if prsl_id not in pi_location_by_prsl:
            pi_location_by_prsl[prsl_id] = get_pi_office_location(proposal)
        pi_location = pi_location_by_prsl[prsl_id]

        panel = proposal_to_panel.get(prsl_id)
        panel_id = panel.panel_id if panel else None
        panel_name = panel.name if panel else None
        assigned = (
            "Yes"
            if panel and any(pp.prsl_id == prsl_id for pp in (panel.proposals or []))
            else "No"
        )

        proposal_common_kwargs = dict(
            prsl_id=proposal.prsl_id,
            title=proposal.proposal_info.title,
            science_category=proposal.proposal_info.science_category,
            proposal_status=proposal.status,
            proposal_type=proposal.proposal_info.proposal_type.main_type,
            proposal_attributes=proposal.proposal_info.proposal_type.attributes or [],
            cycle=proposal.cycle,
            array=_get_array_class(proposal),
            panel_id=panel_id,
            assigned_proposal=assigned,
            panel_name=panel_name,
            decision_id=decision.prsl_id if decision else None,
            recommendation=decision.recommendation if decision else None,
            decision_status=decision.status if decision else None,
            panel_rank=decision.rank if decision else None,
            panel_score=decision.score if decision else None,
            location=pi_location,
        )

        proposal_reviews = reviews_by_prsl.get(prsl_id, [])

        if proposal_reviews:
            for review in proposal_reviews:
                kind = getattr(getattr(review, "review_type", None), "kind", None)
                reviewer_id = getattr(review, "reviewer_id", None)

                reviewer_status = None
                if panel_id and reviewer_id and kind:
                    reviewer_status = reviewer_status_lookup.get(
                        (panel_id, reviewer_id, kind)
                    )

                conflict_flag = (
                    getattr(getattr(review, "review_type", None), "conflict", None)
                    and getattr(review.review_type.conflict, "has_conflict", False)
                    if kind == "Science Review"
                    else False
                )

                review_rank = getattr(
                    getattr(review, "review_type", None), "rank", None
                )

                rows.append(
                    ProposalReportResponse(
                        **proposal_common_kwargs,
                        reviewer_id=reviewer_id,
                        reviewer_status=reviewer_status,
                        review_type=kind,
                        review_status=getattr(review, "status", None),
                        conflict=bool(conflict_flag),
                        review_id=getattr(review, "review_id", None),
                        review_rank=review_rank,
                        comments=getattr(review, "comments", None),
                    )
                )
        else:
            rows.append(ProposalReportResponse(**proposal_common_kwargs))

    return rows
