import logging
from http import HTTPStatus
import random
from typing import List

from fastapi import APIRouter, Query
from ska_oso_services.pht.utils.pht_handler import create_sample_data, join_proposals_panels_reviews_decisions
from ska_oso_services.common import oda
from ska_oso_services.pht.model import ProposalReport
from faker import Faker

fake = Faker()

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/report")







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


@router.get("/", response_model=List[ProposalReport])
def get_report(
    deterministic: bool = Query(False, description="Return a deterministic (repeatable) demo dataset"),
    seed: int | None = Query(None, description="Random seed (for reproducible demo output)")
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


