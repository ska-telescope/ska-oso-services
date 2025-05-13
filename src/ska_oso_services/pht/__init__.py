from fastapi import APIRouter

from ska_oso_services.pht.api import prsls

router = APIRouter(prefix="/pht", tags=["PHT API"])
router.include_router(prsls.router)
