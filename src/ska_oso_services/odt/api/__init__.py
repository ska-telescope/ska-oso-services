from fastapi import APIRouter

from ska_oso_services.odt.api import prjs, sbds

router = APIRouter(prefix="/odt", tags=["ODT API"])
router.include_router(prjs.router)
router.include_router(sbds.router)
