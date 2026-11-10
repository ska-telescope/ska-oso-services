from fastapi import APIRouter

from ska_oso_services.common.api import calibrators, coordinates, visibility

common_router = APIRouter(tags=["Common OSO API endpoints"])
common_router.include_router(coordinates.router)
common_router.include_router(calibrators.router)
common_router.include_router(visibility.router)
