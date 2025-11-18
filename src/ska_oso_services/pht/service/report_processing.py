from collections import defaultdict
from itertools import chain
from typing import Optional
from urllib.parse import quote

from ska_oso_services.pht.models.schemas import ProposalReportResponse
from ska_oso_services.pht.utils.ms_graph import make_graph_call
from ska_oso_services.pht.utils.constants import MS_GRAPH_URL

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



_GRAPH_SELECT_OFFICE = "officeLocation"

def _extract_pi_user_id(proposal) -> Optional[str]:
    """
    Return the user_id (string) of the first principal investigator.
    Works for proposal objects with attributes or dict-like structure.
    """

    # Try attribute-style first: proposal.proposal_info.investigators or proposal.investigators
    investigators = (
        getattr(getattr(proposal, "proposal_info", None), "investigators", None)
        or []
    )

    for inv in investigators:
        # handle dict OR object
        principal_flag = (
            inv.get("principal_investigator")
            if isinstance(inv, dict)
            else getattr(inv, "principal_investigator", None)
        )

        if principal_flag:
            uid = (
                inv.get("user_id")
                if isinstance(inv, dict)
                else getattr(inv, "user_id", None)
            )
            if uid:
                s = str(uid).strip()
                if s:
                    return s

    return None


def get_pi_office_location(proposal) -> Optional[str]:
    """
    Fetch the Microsoft Graph 'officeLocation' for the PI.
    """

    uid = _extract_pi_user_id(proposal)
    if not uid:
        return None

    url = f"{MS_GRAPH_URL}/users/{quote(uid, safe='')}?$select={_GRAPH_SELECT_OFFICE}"
    user = make_graph_call(url, pagination=False) 

    if isinstance(user, dict):
        return user.get("officeLocation")

    return None



def join_proposals_panels_reviews_decisions(
    proposals, panels, reviews, decisions
) -> list[ProposalReportResponse]:
    """Join proposals, panels, reviews, decisions at review_id-level (science/technical), 
    falling back to proposal+decision when no reviews exist. Handles unavailable entities gracefully.
    """
    rows: list[ProposalReportResponse] = []

    # ---- Index panels ----
    panel_by_id = {p.panel_id: p for p in (panels or [])}
    proposal_to_panel = {}
    for p in (panels or []):
        for pp in (p.proposals or []):
            proposal_to_panel[pp.prsl_id] = p

    # ---- Index decisions by proposal ----
    decision_by_pid = {d.prsl_id: d for d in (decisions or [])}

    # ---- Cache PI office location per proposal ----
    pi_location_by_prsl: dict[str, str | None] = {}

    # ---- Index reviews by proposal (we will iterate *each* review row -> review_id-level join) ----
    reviews_by_prsl: dict[str, list] = defaultdict(list)
    for r in (reviews or []):
        reviews_by_prsl[r.prsl_id].append(r)

    # ---- Build reviewer status lookup, kind (Science vs Technical) ----
    # key: (panel_id, reviewer_id, kind) -> status
    reviewer_status_lookup: dict[tuple[str, str, str], str] = {}
    for p in (panels or []):
        # Science reviewers
        for rv in (p.sci_reviewers or []):
            reviewer_status_lookup[(p.panel_id, rv.reviewer_id, "Science Review")] = rv.status
        # Technical reviewers
        for rv in (p.tech_reviewers or []):
            reviewer_status_lookup[(p.panel_id, rv.reviewer_id, "Technical Review")] = rv.status

    # ---- Build rows ----
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
            # Emit one row per review_id (science/technical etc.)
            for review in proposal_reviews:
                kind = getattr(getattr(review, "review_type", None), "kind", None)
                reviewer_id = getattr(review, "reviewer_id", None)

                # Prefer kind-aware reviewer status from panel assignment if available
                reviewer_status = None
                if panel_id and reviewer_id and kind:
                    reviewer_status = reviewer_status_lookup.get((panel_id, reviewer_id, kind))

                # Conflict only meaningful for Science reviews (as per your logic)
                conflict_flag = (
                    getattr(getattr(review, "review_type", None), "conflict", None)
                    and getattr(review.review_type.conflict, "has_conflict", False)
                    if kind == "Science Review"
                    else False
                )

                # Review rank lives under review.review_type.rank if present
                review_rank = getattr(getattr(review, "review_type", None), "rank", None)

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
            # No reviews at all -> fallback to proposal + decision only
            rows.append(ProposalReportResponse(**proposal_common_kwargs))

    return rows