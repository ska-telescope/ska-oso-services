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

# 1. Pydantic Output Model

class ProposalReviewPanelDecisionRow(BaseModel):
    science_category: str
    dummy_col: List[Any] = Field(default_factory=list)
    proposal_id: str
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

# 2. Data Creation

science_categories = ['Cosmology', 'Star Formation', 'Exoplanets', 'Galactic Dynamics']
main_types = ['director_time_proposal', 'special_time_proposal']
status_options = ['submitted', 'decided', 'under review', 'in progress', 'todo', 'draft', 'rejected']
panel_names = ['Stargazers A', 'Stargazers B', 'Stargazers C', 'Stargazers D', 'Stargazers E']
arrays = ['LOW', 'MID', 'BOTH']
recommendations = [
    'Recommend for observation time.',
    'Not recommended at this time.',
    'Recommend for observation time with minor changes.'
]
reviewer_comments = [
    'Well motivated and significant.',
    'Interesting approach, but needs more data.',
    'Strong proposal with clear goals.',
    'Lacks detail in methodology.'
]
reviewers_master = [f"rev-{i}" for i in range(11, 61)]
reviewer_names = [f"Reviewer{i}" for i in range(11, 61)]

def random_datetime(start_days_ago=30):
    dt = fake.date_time_between(start_date=f"-{start_days_ago}d", end_date="now")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def random_date(start_days_ago=30):
    dt = fake.date_between(start_date=f"-{start_days_ago}d", end_date="today")
    return dt.strftime("%a %b %d %Y")

def make_proposal_id(i):
    return f"prsl-t{str(i).zfill(4)}-20250523-000{str(i).zfill(2)}"

def create_sample_data(n_proposals=7):
    proposals, panels, reviews, decisions = [], [], [], []

    # Proposals
    for i in range(1, n_proposals + 1):
        proposals.append({
            "proposal_id": make_proposal_id(i),
            "status": random.choice(status_options),
            "submitted_on": random_date(),
            "info": {
                "title": f"Proposal Title {i}",
                "science_category": random.choice(science_categories),
                "proposal_type": {"main_type": random.choice(main_types)}
            },
            "cycle": "SKA_1962_2024",
            "panel": panel_names[i % len(panel_names)],
            "array": random.choice(arrays)
        })

    # Panels
    for i, p in enumerate(proposals):
        reviewers_in_panel = random.sample(reviewers_master, 4)
        panels.append({
            "panel_id": f"panel-{chr(65 + (i%5))}-2025",
            "name": panel_names[i % len(panel_names)],
            "cycle": "pep-333",
            "proposals": [{
                "proposal_id": p["proposal_id"],
                "assigned_on": random_datetime()
            }],
            "reviewers": [
                {
                    "reviewer_id": rid,
                    "assigned_on": random_datetime(),
                    "status": random.choice(["Accepted", "Declined"])
                } for rid in reviewers_in_panel
            ]
        })

    # Reviews (many per proposal)
    for i, p in enumerate(proposals):
        n_reviews = random.randint(2, 3)
        reviewers_for_this_proposal = random.sample(reviewers_master, n_reviews)
        for j, rid in enumerate(reviewers_for_this_proposal):
            idx = reviewers_master.index(rid)
            reviews.append({
                "review_id": f"revw-{i+1}-{j+1}",
                "panel_id": panels[i]["panel_id"],
                "cycle": panels[i]["cycle"],
                "reviewer_id": rid,
                "proposal_id": p["proposal_id"],
                "rank": round(random.uniform(60, 99), 2),
                "comments": random.choice(reviewer_comments),
                "conflict": {
                    "has_conflict": random.choice([True, False]),
                    "reason": random.choice(["Job", "Ethical", "Lack of knowledge", "None"])
                },
                "submitted_on": random_datetime(),
                "submitted_by": reviewer_names[idx],
                "status": random.choice(['in progress', 'finalized', 'to do', 'decided'])
            })

    # Decisions (one per proposal)
    for i, p in enumerate(proposals):
        panel_id = panels[i]["panel_id"]
        decisions.append({
            "cycle": panels[i]["cycle"],
            "panel_id": panel_id,
            "proposal_id": p["proposal_id"],
            "rank": random.randint(0, 9),
            "recommendation": random.choice(recommendations),
            "status": random.choice(['decided', 'in progress']),
            "decided_by": f"tac-chair-{random.randint(1,20)}",
            "decided_on": random_datetime()
        })
    return proposals, panels, reviews, decisions

# 3. Join/Merge Function (returns list of Pydantic models)

def join_proposals_panels_reviews_decisions(
    proposals, panels, reviews, decisions
) -> List[ProposalReviewPanelDecisionRow]:
    rows = []
    panel_by_id = {p["panel_id"]: p for p in panels}
    proposal_by_id = {p["proposal_id"]: p for p in proposals}
    decision_by_pid = {d["proposal_id"]: d for d in decisions}

    for review in reviews:
        proposal = proposal_by_id.get(review["proposal_id"])
        if not proposal:
            continue
        panel = panel_by_id.get(review["panel_id"])
        decision = decision_by_pid.get(review["proposal_id"])
        reviewer_panel_entry = None
        if panel:
            reviewer_panel_entry = next((r for r in panel["reviewers"] if r["reviewer_id"] == review["reviewer_id"]), None)
        reviewer_status = reviewer_panel_entry["status"] if reviewer_panel_entry else "Pending"

        row = ProposalReviewPanelDecisionRow(
            science_category = proposal["info"]["science_category"],
            dummy_col = [],
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
        )
        rows.append(row)
    return rows

@router.get(
    "/",
    summary="Create a report for admin",
)
def get_report() -> str:
    """
    Creates a new proposal in the ODA
    """

    LOGGER.debug("GET REPORT create")
    #get proposals using Andrey's new query -- need to add an endpoint for this
    #get all panels
    #get all reviews
    #get panel decision

  
    # with oda.uow() as uow:
        # query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        # proposals = uow.prsls.query(query_param)
        # panels = uow.panels.query(query_param)
        # reviews = uow.rvws.query(query_param)
        # panel_decisions = uow.pnlds.query(query_param)
    proposals, panels, reviews, panel_decisions = create_sample_data()
    report = join_proposals_panels_reviews_decisions(proposals, panels, reviews, panel_decisions)
    return report 


