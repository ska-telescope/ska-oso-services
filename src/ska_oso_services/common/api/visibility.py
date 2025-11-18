# app.py
import io, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import Response
from astropy.time import Time
import astropy.units as u
import logging
from fastapi import APIRouter
from ska_oso_services.common.visibility import _render_svg, SITES
from ska_oso_services.common.static.constants import STEP_SECONDS_DEFAULT_VISIBILITY, T10_COLOURS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visibility")


@router.get(
    "/visibility",
    responses={200: {"content": {"image/svg+xml": {}}}},
)
def visibility_svg(
    ra: str = Query(..., description='RA, e.g. "10h00m00s"'),
    dec: str = Query(..., description='Dec, e.g. "-30d00m00s"'),
    array: str = Query(..., description="LOW | MID"),
) -> Response:
    try:
        key = array.upper()
        try:
            site_cfg = SITES[key]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported array '{array}'. Expected one of: {', '.join(SITES.keys())}.",
            )

        svg = _render_svg(
            ra=ra,
            dec=dec,
            site=site_cfg.location,
            min_elev=site_cfg.min_elev_deg,
            step_s=STEP_SECONDS_DEFAULT_VISIBILITY,
        )
        return Response(content=svg, media_type="image/svg+xml")

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid coordinates: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plot error: {exc}") from exc