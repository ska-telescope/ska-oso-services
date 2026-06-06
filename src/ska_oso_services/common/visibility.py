# pylint: disable=no-member
import matplotlib
from astropy.units import Quantity

matplotlib.use("Agg")
import io
from dataclasses import dataclass
from datetime import datetime, timezone

import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time
from matplotlib.ticker import FuncFormatter, MultipleLocator

from ska_oso_services.common.static.constants import STEP_SECONDS_DEFAULT_VISIBILITY, T10_COLOURS


@dataclass(frozen=True)
class SiteConfig:
    location: EarthLocation
    min_elev_deg: float


# Sites
SITES: dict[str, SiteConfig] = {
    "LOW": SiteConfig(
        location=EarthLocation(
            lat=Quantity(-26.82472208, u.deg),
            lon=Quantity(116.7644482, u.deg),
            height=Quantity(377.8, u.m),
        ),
        min_elev_deg=20.0,
    ),
    "MID": SiteConfig(
        location=EarthLocation(
            lat=Quantity(-30.7130, u.deg),
            lon=Quantity(21.4430, u.deg),
            height=Quantity(1000, u.m),
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


def render_svg(
    ra: str,
    dec: str,
    site: EarthLocation,
    min_elev: float,
    step_s: int = STEP_SECONDS_DEFAULT_VISIBILITY,
) -> bytes:
    # Anchor at the UTC time when LST = 0h so the x-axis starts at 0h.
    # LST is then computed as a linear ramp (0 → ~24.07h over one solar day)
    # rather than via astropy's sidereal_time(), which wraps at 24h and would
    # produce discontinuities at both ends of the data array.
    _t_ref = Time(datetime.now(timezone.utc))
    _lst_ref_h = _t_ref.sidereal_time("apparent", longitude=site.lon).hour
    plot_start_time_utc = (_t_ref - (_lst_ref_h / 24.0) * u.sday).to_datetime(
        timezone=timezone.utc
    )

    times, alt = _alts(ra, dec, site, plot_start_time_utc, step_s)
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

    # One solar day advances LST by solar_day/sidereal_day × 24h ≈ 24.066h.
    # Using linspace avoids the 24→0 wrap that astropy's .hour attribute produces.
    lst_hours = np.linspace(0, 24 * (24 * 3600 / u.sday.to(u.s)), len(times))

    # only above horizon
    ax.plot(
        lst_hours,
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

    ax.fill_between(
        lst_hours,
        min_elev,
        alt,
        where=(alt >= min_elev),
        color=T10_COLOURS["teal"],
        alpha=0.18,
    )

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 90)
    ax.grid(False)

    ax.set_title(
        f"Target Visibility: {vis_h}h {vis_m}m above {min_elev:.0f}°",
        pad=10,
    )
    ax.set_ylabel("Elevation (°)", fontsize=14, labelpad=6)
    ax.set_xlabel("LST (hh:mm)", fontsize=14, labelpad=8)

    # Hourly ticks
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda h, _: f"{int(h):02d}:00"))
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
