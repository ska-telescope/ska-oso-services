"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""
# import random
from datetime import datetime, timezone
from typing import List
# from faker import Faker

# fake = Faker()
from pydantic import BaseModel
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.pht.model import ProposalReport

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



def join_proposals_panels_reviews_decisions(
    proposals, panels, reviews, decisions
) -> List[ProposalReport]:
    """Joins all input data into output rows."""
    rows = []
    panel_by_id = {p["panel_id"]: p for p in panels}
    proposal_by_id = {p["prsl_id"]: p for p in proposals}
    decision_by_pid = {d["prsl_id"]: d for d in decisions}
    for review in reviews:
        proposal = proposal_by_id.get(review["prsl_id"])
        if not proposal:
            continue  # Robustness: skip unmatched
        panel = panel_by_id.get(review["panel_id"])
        decision = decision_by_pid.get(review["prsl_id"])
        reviewer_panel_entry = None
        if panel:
            reviewer_panel_entry = next((r for r in panel["reviewers"] if r["reviewer_id"] == review["reviewer_id"]), None)
        reviewer_status = reviewer_panel_entry["status"] if reviewer_panel_entry else "Pending"
        rows.append(ProposalReport(
            science_category = proposal["info"]["science_category"],
            prsl_id = proposal["prsl_id"],
            title = proposal["info"]["title"],
            proposal_status = proposal["status"],
            proposal_attributes = proposal["info"]["proposal_type"].get("attributes", []),
            proposal_type = proposal["info"]["proposal_type"]["main_type"],
            array = proposal["array"],
            cycle = proposal["cycle"],
            panel_id = panel["panel_id"] if panel else None,
            panel_name = panel["name"] if panel else None,
            reviewer_id = review["reviewer_id"],
            reviewer_status = reviewer_status,
            review_status = review["status"],
            conflict = review["conflict"]["has_conflict"],
            review_id = review["review_id"],
            review_rank = review["rank"],
            comments = review["comments"],
            decision_id = decision["prsl_id"] if decision else None,
            recommendation = decision["recommendation"] if decision else None,
            decision_status = decision["status"] if decision else None,
            panel_rank = decision["rank"] if decision else None,
            review_submitted_on = review["submitted_on"],
            decision_on = decision["decided_on"] if decision else None
        ))
    return rows






# class Reviewer(BaseModel):
#     reviewer_id: str
#     name: str


# # ----- CONFIG -----
# SCIENCE_CATEGORIES = ['Cosmology', 'Star Formation', 'Exoplanets', 'Galactic Dynamics']
# PROPOSAL_TYPES = ['director_time_proposal', 'special_time_proposal']
# ARRAYS = ['LOW', 'MID', 'BOTH']
# RECOMMENDATIONS = [
#     'Recommend for observation time.',
#     'Not recommended at this time.',
#     'Recommend for observation time with minor changes.'
# ]


# # ----- MOCKED DATA CREATION with some randomness -----
# def get_reviewer_master(faker: Faker) -> List[Reviewer]:
#     """Return master reviewer list for demo (id+name)."""
#     return [
#         Reviewer(reviewer_id="rev-1", name=faker.name()),
#         Reviewer(reviewer_id="rev-2", name=faker.name()),
#         Reviewer(reviewer_id="rev-3", name=faker.name()),
#         Reviewer(reviewer_id="rev-4", name=faker.name()),
#         Reviewer(reviewer_id="rev-5", name=faker.name()),
#     ]

# def create_sample_data(
#     faker: Faker,
#     deterministic: bool = False
# ):
#     """Creates demo panels, proposals, reviews, and decisions."""
#     reviewers = get_reviewer_master(faker)
#     categories = (["Star Formation", "Cosmology"] if deterministic
#                   else random.sample(SCIENCE_CATEGORIES, 2))
#     titles = (
#         ["Tracing Magnetic Fields in the ISM", "Mapping High-z Galaxies"]
#         if deterministic
#         else [faker.sentence(nb_words=4) for _ in range(2)]
#     )
#     proposal_types = (
#         ["director_time_proposal", "special_time_proposal"] if deterministic
#         else [random.choice(PROPOSAL_TYPES) for _ in range(2)]
#     )
#     proposal_arrays = (
#         ["LOW", "MID"] if deterministic
#         else [random.choice(ARRAYS) for _ in range(2)]
#     )

#     # Panel assignments (with reviewer overlap)
#     panel_reviewers = [
#         [reviewers[0], reviewers[1], reviewers[2]],   # Panel A
#         [reviewers[2], reviewers[3], reviewers[4]],   # Panel B
#     ]
#     panels = []
#     for i, (panel_revs, panel_name) in enumerate(zip(panel_reviewers, ["Stargazers A", "Stargazers B"])):
#         panels.append({
#             "panel_id": f"panel-{chr(65+i)}-2025",
#             "name": panel_name,
#             "cycle": "pep-333",
#             "proposals": [{"prsl_id": f"prsl-t000{i+1}-20250523-0000{i+1}", "assigned_on": faker.iso8601()}],
#             "reviewers": [
#                 {
#                     "reviewer_id": r.reviewer_id,
#                     "assigned_on": faker.iso8601(),
#                     "status": "Accepted"
#                 } for r in panel_revs
#             ]
#         })

#     proposals = []
#     for i in range(2):
#         proposals.append({
#             "prsl_id": f"prsl-t000{i+1}-20250523-0000{i+1}",
#             "status": "submitted" if i == 0 else "under review",
#             "submitted_on": faker.date_this_decade().strftime("%a %b %d %Y"),
#             "info": {
#                 "title": titles[i],
#                 "science_category": categories[i],
#                 "proposal_type": {"main_type": proposal_types[i], "attributes": ["coordinated_proposal"]},
#             },
#             "cycle": "SKA_1962_2024",
#             "panel": panels[i]["name"],
#             "array": proposal_arrays[i]
#         })

#     reviews = []
#     comments_bank = [
#         faker.sentence(nb_words=6),
#         faker.sentence(nb_words=7),
#         faker.sentence(nb_words=8),
#     ]
#     for i, panel in enumerate(panels):
#         prsl_id = panel["proposals"][0]["prsl_id"]
#         for reviewer in panel["reviewers"]:
#             reviewer_name = next(r.name for r in reviewers if r.reviewer_id == reviewer["reviewer_id"])
#             reviews.append({
#                 "review_id": faker.uuid4(),
#                 "panel_id": panel["panel_id"],
#                 "cycle": panel["cycle"],
#                 "reviewer_id": reviewer["reviewer_id"],
#                 "prsl_id": prsl_id,
#                 "rank": round(70 + 10 * random.random(), 1),
#                 "comments": random.choice(comments_bank),
#                 "conflict": {"has_conflict": False, "reason": "None"},
#                 "submitted_on": faker.iso8601(),
#                 "submitted_by": reviewer_name,
#                 "status": "decided" if i == 0 else "under review"
#             })

#     decisions = []
#     for i, proposal in enumerate(proposals):
#         panel_id = panels[i]["panel_id"]
#         decisions.append({
#             "cycle": "pep-333",
#             "panel_id": panel_id,
#             "prsl_id": proposal["prsl_id"],
#             "rank": random.randint(1, 5),
#             "recommendation": random.choice(RECOMMENDATIONS),
#             "status": "decided",
#             "decided_by": faker.name(),
#             "decided_on": faker.iso8601()
#         })
#     return proposals, panels, reviews, decisions


