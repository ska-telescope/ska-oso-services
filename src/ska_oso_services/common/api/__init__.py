from fastapi import APIRouter

from ska_oso_services.common.api import coordinates

common_router = APIRouter(tags=["Common OSO API endpoints"])
common_router.include_router(coordinates.router)
