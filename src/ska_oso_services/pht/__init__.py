from fastapi import APIRouter

from ska_oso_services.pht.api import panels, prsls, reviewers

router = APIRouter(prefix="/pht", tags=["PHT API"])
router.include_router(prsls.router)
router.include_router(reviewers.router)
router.include_router(panels.router)
