import logging

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
) -> Response:
    try:
        key = array.upper()
        site_cfg = SITES[key]

        svg = render_svg(
            ra=ra,
            dec=dec,
            site=site_cfg.location,
            min_elev=site_cfg.min_elev_deg,
            step_s=STEP_SECONDS_DEFAULT_VISIBILITY,
        )
        return Response(content=svg, media_type="image/svg+xml")

    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Invalid coordinates: {error}") from error
