from fastapi import APIRouter

from ska_oso_services.pht.api import ppt
router = APIRouter(prefix="/pht", tags=["PPT API"])
router.include_router(ppt.router)
