from fastapi import APIRouter

from ska_oso_services.pht.api import panel_decision, prsls, reviewers, reviews

router = APIRouter(prefix="/pht", tags=["PHT API"])
router.include_router(prsls.router)
router.include_router(reviewers.router)
router.include_router(reviews.router)
router.include_router(panel_decision.router)
