from fastapi import APIRouter

from ska_oso_services.engineering.api import ebs

router = APIRouter(prefix="/engineering", tags=["Engineering API"])
router.include_router(ebs.router)
