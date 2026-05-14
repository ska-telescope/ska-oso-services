from http import HTTPStatus
from os import getenv

from fastapi import APIRouter

from ska_oso_services.common.error_handling import _make_json_response
from ska_oso_services.common.model import ErrorResponse
from ska_oso_services.engineering.api import ebs

router = APIRouter(prefix="/engineering", tags=["Engineering API"])

ENGINEERING_API_ENABLED = getenv("ENGINEERING_API_ENABLED", "true").lower() == "true"


async def engineering_api_disabled():
    return _make_json_response(
        ErrorResponse(
            status=HTTPStatus.NOT_IMPLEMENTED,
            title="Engineering API not enabled",
            detail="The engineering API is not enabled in this deployment.",
        )
    )


if ENGINEERING_API_ENABLED:
    router.include_router(ebs.router)
else:
    router.add_api_route(
        path="/{path:path}",
        endpoint=engineering_api_disabled,
        methods=["GET", "POST", "PUT", "PATCH"],
    )
