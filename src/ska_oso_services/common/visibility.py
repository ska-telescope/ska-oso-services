from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import io

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u
from ska_oso_services.common.static.constants import STEP_SECONDS_DEFAULT_VISIBILITY, T10_COLOURS





@dataclass(frozen=True)
class SiteConfig:
    location: EarthLocation
    min_elev_deg: float


# Sites
SITES: dict[str, SiteConfig] = {
    "LOW": SiteConfig(
        location=EarthLocation(
            lat=-26.82472208 * u.deg,
            lon=116.7644482 * u.deg,
            height=377.8 * u.m,
        ),
        min_elev_deg=20.0,
    ),
    "MID": SiteConfig(
        location=EarthLocation(
            lat=-30.7130 * u.deg,
            lon=21.4430 * u.deg,
            height=1000 * u.m,
        ),
        min_elev_deg=15.0,
    ),
}


def _alts(
    ra: str,
    dec: str,
    site: EarthLocation,
    start: datetime,
    step_s: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute altitude (deg) vs time over 24 hours."""
    seconds_per_day = 24 * 3600
    n = seconds_per_day // step_s + 1

    times = Time(start) + (np.linspace(0, seconds_per_day, n) * u.s)
    coords = SkyCoord(ra=ra, dec=dec, unit=(u.hourangle, u.deg), frame="icrs")
    alt = coords.transform_to(AltAz(obstime=times, location=site)).alt.to_value(u.deg)

    return np.array(times.to_datetime(timezone=timezone.utc)), alt


def _visible_duration(alt: np.ndarray, min_elev: float, step_s: int) -> tuple[int, int, int]:
    """Return total visible time as (seconds, hours, minutes)."""
    seconds = int((alt >= min_elev).sum() * step_s)
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return seconds, hours, minutes


def _render_svg(
    ra: str,
    dec: str,
    site: EarthLocation,
    min_elev: float,
    step_s: int = STEP_SECONDS_DEFAULT_VISIBILITY,
) -> bytes:
    # Inline midnight-UTC calculation
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = base + timedelta(days=1)

    times, alt = _alts(ra, dec, site, base, step_s)
    _, vis_h, vis_m = _visible_duration(alt, min_elev, step_s)

    # Matte style
    plt.rcParams.update(
        {
            "axes.facecolor": "#ffffff",
            "figure.facecolor": "#ffffff",
            "axes.edgecolor": "#e5e7eb",
            "axes.linewidth": 1.0,
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "font.size": 11,
            "path.simplify": False,
        }
    )

    fig, ax = plt.subplots(figsize=(12, 6.2))

    # Curve (only above horizon)
    ax.plot(
        times,
        np.where(alt >= 0, alt, np.nan),
        color=T10_COLOURS["blue"],
        lw=2.2,
        antialiased=True,
        solid_capstyle="round",
        solid_joinstyle="round",
        label="Elevation (°)",
    )

    # Min elevation threshold
    ax.axhline(
        min_elev,
        color=T10_COLOURS["red"],
        ls="--",
        lw=1.3,
        label=f"Min elevation ({min_elev:.0f}°)",
    )

    # Visible region fill
    ax.fill_between(
        times,
        min_elev,
        alt,
        where=(alt >= min_elev),
        color=T10["teal"],
        alpha=0.18,
    )

    ax.set_xlim(base, end)
    ax.set_ylim(0, 90)
    ax.grid(False)

    ax.set_title(
        f"Visibility on {base.date()} (UTC): {vis_h}h {vis_m}m above {min_elev:.0f}°",
        pad=10,
    )
    ax.set_ylabel("Elevation (°)", fontsize=14, labelpad=6)
    ax.set_xlabel("Time (UTC)", fontsize=14, labelpad=8)

    # Hourly ticks
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    ax.tick_params(axis="both", which="major", labelsize=11)

    for label in ax.get_xticklabels():
        label.set_rotation(35)
        label.set_ha("right")

    legend = ax.legend(loc="upper left", frameon=True)
    legend.get_frame().set_edgecolor("#e5e7eb")
    fig.subplots_adjust(bottom=0.2)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)

    return buf.getvalue()