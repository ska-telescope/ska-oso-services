from fastapi import APIRouter

from ska_oso_services.pht.api import pht

router = APIRouter(prefix="/pht", tags=["PHT API"])
router.include_router(pht.router)
