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
    ra: str = Query(None, description="RA, e.g. 05:34:31.7760"),
    dec: str = Query(None, description="Dec, e.g. 22:01:02.640"),
    l: str = Query(None, description="Galactic longitude e.g. 184.5547"),
    b: str = Query(None, description="Galactic latitude e.g. -5.7833"),
    coord_system: str = Query("ICRS", description="ICRS | Galactic"),
    array: str = Query(..., description="LOW | MID"),
    show_ateam: bool = Query(True, description="Overlay A-team source elevations and separations"),
) -> Response:
    key = array.upper()
    if key not in SITES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unknown array '{array}'. Must be one of: {', '.join(SITES)}",
        )

    coord_system = coord_system.upper()

    try:
        match coord_system:
            case "ICRS":
                svg = render_svg(
                    ra=ra,
                    dec=dec,
                    site_key=key,
                    step_s=STEP_SECONDS_DEFAULT_VISIBILITY,
                    show_ateam=show_ateam,
                )
                return Response(content=svg, media_type="image/svg+xml")

            case "GALACTIC":
                svg = render_svg(
                    l=float(l),
                    b=float(b),
                    site_key=key,
                    step_s=STEP_SECONDS_DEFAULT_VISIBILITY,
                    show_ateam=show_ateam,
                )
                return Response(content=svg, media_type="image/svg+xml")

            case _:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Unknown coordinate system '{coord_system}'."
                    " Must be either ICRS or Galactic",
                )

    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=f"Invalid coordinates: {error}"
        ) from error
