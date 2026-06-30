# pylint: disable=no-member
import matplotlib
from astropy.units import Quantity

matplotlib.use("Agg")
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

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

# A-team sources visible from SKA-Low (ICRS)
ATEAM_SOURCES: dict[str, tuple[str, str]] = {
    "Centaurus A": ("13h25m27.6152s", "-43d01m08.805s"),
    "Fornax A": ("03h22m41.7890s", "-37d12m29.520s"),
    "Pictor A": ("05h19m49.7229s", "-45d46m43.853s"),
    "Hydra A": ("09h18m05.6685s", "-12d05m43.806s"),
    "Virgo A": ("12h30m49.4234s", "+12d23m28.044s"),
    "Taurus A": ("05h34m31.7760s", "+22d01m02.640s"),
    "Cygnus A": ("19h59m28.3566s", "+40d44m02.097s"),
    "Hercules A": ("16h51m07.9887s", "+04d59m35.547s"),
    "Cassiopeia A": ("23h23m26.0160s", "+58d48m40.680s"),
}

# Okabe-Ito palette (colour vision deficiency safe) + Grey for the 9 A-team sources
_ATEAM_COLOURS = [
    "#000000",
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#999999",
]


class AteamLineStyle(Enum):
    LONG_DASH = (0, (8, 2))
    MEDIUM_DASH = (0, (4, 2))
    DOTTED = (0, (1, 2))
    DASH_DOT = (0, (4, 2, 1, 2))
    DASH_DOT_DOT = (0, (4, 2, 1, 2, 1, 2))
    LONG_DASH_DOT = (0, (8, 2, 1, 2))
    SHORT_DASH = (0, (2, 2))
    LONG_MEDIUM_DASH = (0, (8, 2, 4, 2))
    DENSELY_DOTTED = (0, (1, 1))


def _alts(
    sky_coord: SkyCoord,
    site: EarthLocation,
    start: datetime,
    step_s: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute altitude (deg) vs time over 24 hours."""
    seconds_per_day = 24 * 3600
    n = seconds_per_day // step_s + 1

    times = Time(start) + (np.linspace(0, seconds_per_day, n) * u.s)
    alt = sky_coord.transform_to(AltAz(obstime=times, location=site)).alt.to_value(u.deg)

    return np.array(times.to_datetime(timezone=timezone.utc)), alt


def _visible_duration(alt: np.ndarray, min_elev: float, step_s: int) -> tuple[int, int, int]:
    """Return total visible time as (seconds, hours, minutes)."""
    seconds = int((alt >= min_elev).sum() * step_s)
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return seconds, hours, minutes


_REF_EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _precompute_ateam_alts(site: EarthLocation) -> dict[str, np.ndarray]:
    t_ref = Time(_REF_EPOCH)
    lst_ref_h = t_ref.sidereal_time("apparent", longitude=site.lon).hour
    start = (t_ref - (lst_ref_h / 24.0) * u.sday).to_datetime(timezone=timezone.utc)
    return {
        name: _alts(
            SkyCoord(ra=ra, dec=dec, units=(u.hourangle, u.deg), frame="icrs"),
            site,
            start,
            STEP_SECONDS_DEFAULT_VISIBILITY,
        )[1]
        for name, (ra, dec) in ATEAM_SOURCES.items()
    }


_ATEAM_ALTS: dict[str, dict[str, np.ndarray]] = {}


def _get_ateam_alts(site_key: str) -> dict[str, np.ndarray]:
    if site_key not in _ATEAM_ALTS:
        _ATEAM_ALTS[site_key] = _precompute_ateam_alts(SITES[site_key].location)
    return _ATEAM_ALTS[site_key]


def render_svg(
    ra: str | None = None,
    dec: str | None = None,
    l: float | None = None,
    b: float | None = None,
    site_key: str = "",
    step_s: int = STEP_SECONDS_DEFAULT_VISIBILITY,
    show_ateam: bool = True,
) -> bytes:

    site_cfg = SITES[site_key]
    site = site_cfg.location
    min_elev = site_cfg.min_elev_deg

    # Anchor at the UTC time when LST = 0h so the x-axis starts at 0h.
    # LST is then computed as a linear ramp (0 → ~24.07h over one solar day)
    # rather than via astropy's sidereal_time(), which wraps at 24h and would
    # produce discontinuities at both ends of the data array.
    _t_ref = Time(datetime.now(timezone.utc))
    _lst_ref_h = _t_ref.sidereal_time("apparent", longitude=site.lon).hour
    plot_start_time_utc = (_t_ref - (_lst_ref_h / 24.0) * u.sday).to_datetime(
        timezone=timezone.utc
    )

    if ra is not None and dec is not None:
        target_coord = SkyCoord(
            ra=ra,
            dec=dec,
            unit=(u.hourangle, u.deg),
            frame="icrs",
        )
    elif l is not None and b is not None:
        target_coord = SkyCoord(
            l=l,
            b=b,
            unit=(u.deg, u.deg),
            frame="galactic",
        )
    else:
        raise ValueError("Must provide either (ra, dec) or (l, b)")

    times, alt = _alts(target_coord, site, plot_start_time_utc, step_s)

    # One solar day advances LST by solar_day/sidereal_day × 24h ≈ 24.066h.
    # Using linspace avoids the 24→0 wrap that astropy's .hour attribute produces.
    lst_hours = np.linspace(0, 24 * (24 * 3600 / u.sday.to(u.s)), len(times))

    # Compute visibility only for samples within the displayed LST range (0–24h).
    _, vis_h, vis_m = _visible_duration(alt[lst_hours <= 24], min_elev, step_s)

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

    # only above horizon
    ax.plot(
        lst_hours,
        np.where(alt >= 0, alt, np.nan),
        color=T10_COLOURS["blue"],
        lw=2.2,
        antialiased=True,
        solid_capstyle="round",
        solid_joinstyle="round",
        label="Target",
    )

    # Min elevation threshold
    ax.axhline(
        min_elev,
        color=T10_COLOURS["red"],
        ls="--",
        lw=1.3,
        label=f"Elevation limit: {min_elev:.0f}°",
    )

    ax.fill_between(
        lst_hours,
        min_elev,
        alt,
        where=(alt >= min_elev),
        color=T10_COLOURS["teal"],
        alpha=0.18,
    )

    if show_ateam:
        use_cache = step_s == STEP_SECONDS_DEFAULT_VISIBILITY
        for (name, (src_ra, src_dec)), line_style, colour in zip(
            ATEAM_SOURCES.items(), AteamLineStyle, _ATEAM_COLOURS
        ):
            ateam_coord = SkyCoord(ra=src_ra, dec=src_dec, unit=(u.hourangle, u.deg), frame="icrs")
            sep_deg = target_coord.separation(ateam_coord).deg
            src_alt = (
                _get_ateam_alts(site_key)[name]
                if use_cache
                else _alts(ateam_coord, site, plot_start_time_utc, step_s)[1]
            )
            ax.plot(
                lst_hours,
                np.where(src_alt >= 0, src_alt, np.nan),
                color=colour,
                ls=line_style.value,
                lw=1.0,
                alpha=0.6,
                antialiased=True,
                label=f"{name}  (sep = {sep_deg:.1f}°)",
            )

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 90)
    ax.grid(False)

    ax.set_title(
        f"The target is over the elevation limit of {min_elev:.0f}° for {vis_h}h {vis_m}m",
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

    legend = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncols=3,
        frameon=True,
    )
    legend.get_frame().set_edgecolor("#e5e7eb")
    fig.subplots_adjust(bottom=0.2)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)

    return buf.getvalue()
