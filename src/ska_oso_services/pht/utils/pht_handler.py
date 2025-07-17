"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

# import random
from datetime import datetime, timezone
from typing import List

from ska_oso_pdm.proposal import Proposal

from ska_oso_services.pht.model import ProposalReport

EXAMPLE_OSD_DATA = {
    "observatory_policy": {
        "cycle_number": 1,
        "cycle_description": "Science Verification",
        "cycle_information": {
            "cycle_id": "SKAO_2027_1",
            "proposal_open": "20260327T12:00:00.000Z",
            "proposal_close": "20260512T15:00:00.000z",
        },
        "cycle_policies": {"normal_max_hours": 100.0},
        "telescope_capabilities": {"Mid": "AA2", "Low": "AA2"},
    },
    "capabilities": {
        "mid": {
            "basic_capabilities": {
                "dish_elevation_limit_deg": 15.0,
                "receiver_information": [
                    {
                        "rx_id": "Band_1",
                        "min_frequency_hz": 350000000.0,
                        "max_frequency_hz": 1050000000.0,
                    },
                    {
                        "rx_id": "Band_2",
                        "min_frequency_hz": 950000000.0,
                        "max_frequency_hz": 1760000000.0,
                    },
                    {
                        "rx_id": "Band_3",
                        "min_frequency_hz": 1650000000.0,
                        "max_frequency_hz": 3050000000.0,
                    },
                    {
                        "rx_id": "Band_4",
                        "min_frequency_hz": 2800000000.0,
                        "max_frequency_hz": 5180000000.0,
                    },
                    {
                        "rx_id": "Band_5a",
                        "min_frequency_hz": 4600000000.0,
                        "max_frequency_hz": 8500000000.0,
                    },
                    {
                        "rx_id": "Band_5b",
                        "min_frequency_hz": 8300000000.0,
                        "max_frequency_hz": 15400000000.0,
                    },
                ],
            },
            "AA2": {
                "available_receivers": ["Band_1", "Band_2", "Band_5a", "Band_5b"],
                "number_ska_dishes": 64,
                "number_meerkat_dishes": 4,
                "number_meerkatplus_dishes": 0,
                "max_baseline_km": 110.0,
                "available_bandwidth_hz": 800000000.0,
                "number_channels": 14880,
                "cbf_modes": ["CORR", "PST_BF", "PSS_BF"],
                "number_zoom_windows": 16,
                "number_zoom_channels": 14880,
                "number_pss_beams": 384,
                "number_pst_beams": 6,
                "ps_beam_bandwidth_hz": 800000000.0,
                "number_fsps": 4,
            },
        },
        "low": {
            "basic_capabilities": {
                "min_frequency_hz": 50000000.0,
                "max_frequency_hz": 350000000.0,
            },
            "AA2": {
                "number_stations": 64,
                "number_substations": 720,
                "number_beams": 8,
                "max_baseline_km": 40.0,
                "available_bandwidth_hz": 150000000.0,
                "channel_width_hz": 5400,
                "cbf_modes": ["vis", "pst", "pss"],
                "number_zoom_windows": 16,
                "number_zoom_channels": 1800,
                "number_pss_beams": 30,
                "number_pst_beams": 4,
                "number_vlbi_beams": 0,
                "ps_beam_bandwidth_hz": 118000000.0,
                "number_fsps": 10,
            },
        },
    },
}

EXAMPLE_PROPOSAL = {
    "prsl_id": "prp-ska01-202204-02",
    "status": "draft",
    "cycle": "5000_2023",
    "info": {
        "title": "The Milky Way View",
        "proposal_type": {
            "main_type": "standard_proposal",
            "attributes": ["coordinated_proposal"],
        },
    },
}


def transform_update_proposal(data: Proposal) -> Proposal:
    """
    Transforms and updates a given Proposal model.

    - If prsl_id is "new", sets it to "12345".
    - Sets submitted_on to now if submitted_by is provided.
    - Sets status based on presence of submitted_on.
    - Extracts investigator_refs from info.investigators.
    """

    # TODO : rethink the logic here - may need to move to UI
    if data.submitted_by:
        submitted_on = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "submitted"
    else:
        submitted_on = data.submitted_on
        status = "submitted" if submitted_on else "draft"

    investigator_refs = [inv.investigator_id for inv in data.info.investigators]

    return Proposal(
        prsl_id=data.prsl_id,
        cycle=data.cycle,
        submitted_by=data.submitted_by,
        submitted_on=submitted_on,
        status=status,
        info=data.info,
        investigator_refs=investigator_refs,
    )


def get_latest_entity_by_id(entities, entity_id: str) -> list:
    """Returns the latest version of each entity based on a unique identifier.

    Args:
        entities ([type]): The list of entities to filter
        entity_id (str): The unique identifier for each entity

    Returns:
        list: of entities with the latest version for each unique entity ID
    """
    latest = {}
    for entity in entities:
        key = getattr(entity, entity_id)
        version = entity.metadata.version
        if key not in latest or version > latest[key].metadata.version:
            latest[key] = entity
    return list(latest.values())


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
) -> List[ProposalReport]:
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
                    ProposalReport(
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
                        panel_name=panel.name,
                        reviewer_id=reviewer_id,
                        reviewer_status=reviewer_status,
                        review_status=review.status if review else None,
                        conflict=(
                            review.conflict.has_conflict
                            if review and review.conflict
                            else False
                        ),
                        review_id=review.review_id if review else None,
                        review_rank=review.rank if review else None,
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
                ProposalReport(
                    prsl_id=proposal.prsl_id,
                    title=proposal.info.title,
                    science_category=proposal.info.science_category,
                    proposal_status=proposal.status,
                    proposal_type=proposal.info.proposal_type.main_type,
                    proposal_attributes=proposal.info.proposal_type.attributes or [],
                    cycle=proposal.cycle,
                    array=_get_array_class(proposal),
                    panel_id=panel.panel_id if panel else None,
                    panel_name=panel.name if panel else None,
                    decision_id=decision.prsl_id if decision else None,
                    recommendation=decision.recommendation if decision else None,
                    decision_status=decision.status if decision else None,
                    panel_rank=decision.rank if decision else None,
                    decision_on=(
                        decision.decided_on.isoformat()
                        if decision and decision.decided_on
                        else None
                    ),
                )
            )

    return rows
