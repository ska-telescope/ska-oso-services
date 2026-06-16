import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ska_oso_services.common.static.constants import STEP_SECONDS_DEFAULT_VISIBILITY
from ska_oso_services.common.visibility import SITES, render_svg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visibility")


@router.get(
    "/visibility",
    responses={200: {"content": {"image/svg+xml": {}}}},
)
def visibility_svg(
    ra: str = Query(..., description="RA, e.g. 05:34:31.7760"),
    dec: str = Query(..., description="Dec, e.g. 22:01:02.640"),
    array: str = Query(..., description="LOW | MID"),
    show_ateam: bool = Query(True, description="Overlay A-team source elevations and separations"),
) -> Response:
    key = array.upper()
    if key not in SITES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unknown array '{array}'. Must be one of: {', '.join(SITES)}",
        )

    try:
        svg = render_svg(
            ra=ra,
            dec=dec,
            site_key=key,
            step_s=STEP_SECONDS_DEFAULT_VISIBILITY,
            show_ateam=show_ateam,
        )
        return Response(content=svg, media_type="image/svg+xml")

    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=f"Invalid coordinates: {error}"
        ) from error
