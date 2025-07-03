from fastapi import APIRouter

from ska_oso_services.pht.api import prsls, reviewers, reviews, panel_decision

router = APIRouter(prefix="/pht", tags=["PHT API"])
router.include_router(prsls.router)
router.include_router(reviewers.router)
router.include_router(reviews.router)
router.include_router(panel_decision.router)
