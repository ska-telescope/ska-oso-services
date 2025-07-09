import logging
from http import HTTPStatus

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError
)
from ska_oso_services.pht.model import EmailRequest
from ska_oso_services.pht.utils import validation
from ska_oso_services.pht.utils.email_helper import send_email_async
from ska_oso_services.pht.utils.pht_handler import (
    EXAMPLE_PROPOSAL,
    transform_update_proposal,
)


LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/report")

from fastapi import FastAPI
from typing import List, Optional, Any
from pydantic import BaseModel, Field
import random
from faker import Faker

fake = Faker()

# ----- CONFIG -----
SCIENCE_CATEGORIES = ['Cosmology', 'Star Formation', 'Exoplanets', 'Galactic Dynamics']
PROPOSAL_TYPES = ['director_time_proposal', 'special_time_proposal']
ARRAYS = ['LOW', 'MID', 'BOTH']
RECOMMENDATIONS = [
    'Recommend for observation time.',
    'Not recommended at this time.',
    'Recommend for observation time with minor changes.'
]

# ----- SCHEMAS -----
class Reviewer(BaseModel):
    reviewer_id: str
    name: str

class ProposalReviewPanelDecisionRow(BaseModel):
    proposal_id: str
    science_category: str
    proposal_status: str
    array: str
    reviewer_comment: str
    reviewer_decision: str
    recommendation: Optional[str]
    decision_status: Optional[str]
    reviewer_name: str
    proposal_type: str
    review_submitted_on: str
    proposal_title: str
    proposal_review_status: str
    reviewer_id: str
    reviewer_rank: float
    panel_name: Optional[str]
    proposal_submitted_on: str
    panel_rank: Optional[int]
    panel_id: Optional[str]
    conflict: bool
    reviewer_accepted: bool
    cycle: str
    decision_on: Optional[str]

# ----- DATA CREATION -----
def get_reviewer_master(faker: Faker) -> List[Reviewer]:
    """Return master reviewer list for demo (id+name)."""
    return [
        Reviewer(reviewer_id="rev-1", name=faker.name()),
        Reviewer(reviewer_id="rev-2", name=faker.name()),
        Reviewer(reviewer_id="rev-3", name=faker.name()),
        Reviewer(reviewer_id="rev-4", name=faker.name()),
        Reviewer(reviewer_id="rev-5", name=faker.name()),
    ]

def create_sample_data(
    faker: Faker,
    deterministic: bool = False
):
    """Creates demo panels, proposals, reviews, and decisions."""
    reviewers = get_reviewer_master(faker)
    categories = (["Star Formation", "Cosmology"] if deterministic
                  else random.sample(SCIENCE_CATEGORIES, 2))
    titles = (
        ["Tracing Magnetic Fields in the ISM", "Mapping High-z Galaxies"]
        if deterministic
        else [faker.sentence(nb_words=4) for _ in range(2)]
    )
    proposal_types = (
        ["director_time_proposal", "special_time_proposal"] if deterministic
        else [random.choice(PROPOSAL_TYPES) for _ in range(2)]
    )
    proposal_arrays = (
        ["LOW", "MID"] if deterministic
        else [random.choice(ARRAYS) for _ in range(2)]
    )

    # Panel assignments (with reviewer overlap)
    panel_reviewers = [
        [reviewers[0], reviewers[1], reviewers[2]],   # Panel A
        [reviewers[2], reviewers[3], reviewers[4]],   # Panel B
    ]
    panels = []
    for i, (panel_revs, panel_name) in enumerate(zip(panel_reviewers, ["Stargazers A", "Stargazers B"])):
        panels.append({
            "panel_id": f"panel-{chr(65+i)}-2025",
            "name": panel_name,
            "cycle": "pep-333",
            "proposals": [{"proposal_id": f"prsl-t000{i+1}-20250523-0000{i+1}", "assigned_on": faker.iso8601()}],
            "reviewers": [
                {
                    "reviewer_id": r.reviewer_id,
                    "assigned_on": faker.iso8601(),
                    "status": "Accepted"
                } for r in panel_revs
            ]
        })

    proposals = []
    for i in range(2):
        proposals.append({
            "proposal_id": f"prsl-t000{i+1}-20250523-0000{i+1}",
            "status": "submitted" if i == 0 else "under review",
            "submitted_on": faker.date_this_decade().strftime("%a %b %d %Y"),
            "info": {
                "title": titles[i],
                "science_category": categories[i],
                "proposal_type": {"main_type": proposal_types[i]}
            },
            "cycle": "SKA_1962_2024",
            "panel": panels[i]["name"],
            "array": proposal_arrays[i]
        })

    reviews = []
    comments_bank = [
        faker.sentence(nb_words=6),
        faker.sentence(nb_words=7),
        faker.sentence(nb_words=8),
    ]
    for i, panel in enumerate(panels):
        proposal_id = panel["proposals"][0]["proposal_id"]
        for reviewer in panel["reviewers"]:
            reviewer_name = next(r.name for r in reviewers if r.reviewer_id == reviewer["reviewer_id"])
            reviews.append({
                "review_id": faker.uuid4(),
                "panel_id": panel["panel_id"],
                "cycle": panel["cycle"],
                "reviewer_id": reviewer["reviewer_id"],
                "proposal_id": proposal_id,
                "rank": round(70 + 10 * random.random(), 1),
                "comments": random.choice(comments_bank),
                "conflict": {"has_conflict": False, "reason": "None"},
                "submitted_on": faker.iso8601(),
                "submitted_by": reviewer_name,
                "status": "decided" if i == 0 else "under review"
            })

    decisions = []
    for i, proposal in enumerate(proposals):
        panel_id = panels[i]["panel_id"]
        decisions.append({
            "cycle": "pep-333",
            "panel_id": panel_id,
            "proposal_id": proposal["proposal_id"],
            "rank": random.randint(1, 5),
            "recommendation": random.choice(RECOMMENDATIONS),
            "status": "decided",
            "decided_by": faker.name(),
            "decided_on": faker.iso8601()
        })
    return proposals, panels, reviews, decisions

# ----- JOIN FUNCTION -----
def join_proposals_panels_reviews_decisions(
    proposals, panels, reviews, decisions
) -> List[ProposalReviewPanelDecisionRow]:
    """Joins all input data into output rows."""
    rows = []
    panel_by_id = {p["panel_id"]: p for p in panels}
    proposal_by_id = {p["proposal_id"]: p for p in proposals}
    decision_by_pid = {d["proposal_id"]: d for d in decisions}
    for review in reviews:
        proposal = proposal_by_id.get(review["proposal_id"])
        if not proposal:
            continue  # Robustness: skip unmatched
        panel = panel_by_id.get(review["panel_id"])
        decision = decision_by_pid.get(review["proposal_id"])
        reviewer_panel_entry = None
        if panel:
            reviewer_panel_entry = next((r for r in panel["reviewers"] if r["reviewer_id"] == review["reviewer_id"]), None)
        reviewer_status = reviewer_panel_entry["status"] if reviewer_panel_entry else "Pending"
        rows.append(ProposalReviewPanelDecisionRow(
            science_category = proposal["info"]["science_category"],
            proposal_id = proposal["proposal_id"],
            proposal_status = proposal["status"],
            array = proposal["array"],
            reviewer_comment = review["comments"],
            reviewer_decision = reviewer_status,
            recommendation = decision["recommendation"] if decision else None,
            decision_status = decision["status"] if decision else None,
            reviewer_name = review["submitted_by"],
            proposal_type = proposal["info"]["proposal_type"]["main_type"],
            review_submitted_on = review["submitted_on"],
            proposal_title = proposal["info"]["title"],
            proposal_review_status = review["status"],
            reviewer_id = review["reviewer_id"],
            reviewer_rank = review["rank"],
            panel_name = panel["name"] if panel else None,
            proposal_submitted_on = proposal["submitted_on"],
            panel_rank = decision["rank"] if decision else None,
            panel_id = panel["panel_id"] if panel else None,
            conflict = review["conflict"]["has_conflict"],
            reviewer_accepted = reviewer_status == "Accepted",
            cycle = proposal["cycle"],
            decision_on = decision["decided_on"] if decision else None
        ))
    return rows


# @router.get(
#     "/",
#     summary="Create a report for admin",
# )
# def get_report() -> List[ProposalReviewPanelDecisionRow]:
#     """
#     Creates a new proposal in the ODA
#     """

#     LOGGER.debug("GET REPORT create")
#     #get proposals using Andrey's new query -- need to add an endpoint for this
#     #get all panels
#     #get all reviews
#     #get panel decision

  
#     # with oda.uow() as uow:
#         # query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
#         # proposals = uow.prsls.query(query_param)
#         # panels = uow.panels.query(query_param)
#         # reviews = uow.rvws.query(query_param)
#         # panel_decisions = uow.pnlds.query(query_param)
#     proposals, panels, reviews, panel_decisions = create_sample_data()
#     report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, panel_decisions)
#     return report 

from fastapi import FastAPI, Query

@router.get("/", response_model=List[ProposalReviewPanelDecisionRow])
def get_report(
    deterministic: bool = Query(False, description="Return a deterministic (repeatable) demo dataset"),
    seed: Optional[int] = Query(None, description="Random seed (for reproducible demo output)")
):
    """
    Get the flattened proposal/panel/review/decision data for the dashboard.
    """
    # Use the provided seed for reproducibility
    if seed is not None:
        random.seed(seed)
        faker = Faker()
        faker.seed_instance(seed)
    else:
        faker = Faker()
    proposals, panels, reviews, decisions = create_sample_data(faker, deterministic=deterministic)
    return join_proposals_panels_reviews_decisions(proposals, panels, reviews, decisions)


