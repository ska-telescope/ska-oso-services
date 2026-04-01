# pylint: disable=no-member
from __future__ import annotations

import logging
from importlib import resources
from typing import Literal, NamedTuple

import astropy.units as u
import numpy as np
from astropy.constants import c as speed_of_light  # pylint: disable=E0611
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_sun
from astropy.table import Row, Table
from astropy.time import Time
from astropy.units import Quantity

from ska_oso_services.odt.service.commissioning import data

logger = logging.getLogger(__name__)

CBFMode = Literal["VIS", "PST"]
COARSE_CHAN_SEP_MHZ = 400 / 512


class Targets(NamedTuple):
    """Cal sweep targets"""

    primary: Row | None
    """Primary target source"""
    secondary: Table | None
    """Secondary targets"""


def coarse_channel_to_freq(coarse_channel: int) -> float:
    """
    Convert coarse channel to frequency.

    :param coarse_channel: Coarse channel number.

    :return: Frequency in MHz
    """
    return COARSE_CHAN_SEP_MHZ * coarse_channel


def station_beam_size(
    obs_freq: u.Quantity[u.MHz], station_diameter: u.Quantity[u.m] = Quantity(38, u.m)
) -> u.Quantity[u.deg]:
    """
    Estimate beam size FWHM.

    :param obs_freq: Observing frequency.
    :param station_diameter: Station diameter. Defaults to 38*u.m.

    :return: Primary beam FWHM
    """
    return (1.027 * u.rad * ((speed_of_light / obs_freq) / station_diameter)).to(u.deg)


def pick_targets(
    coarse_channel_start: int,
    mode: CBFMode = "VIS",
    alt_limit: u.Quantity[u.deg] | None = None,
    obs_time: Time | None = None,
) -> Targets:
    """
    Pick observing targets.

    :param coarse_channel_start: Starting coarse channel.
    :param mode: CBF mode - "VIS" or "PST". Defaults to "VIS".
    :param alt_limit: Elevation limit. Defaults to 30*u.deg.
    :param obs_time: Observing time. Defaults to None.

    :raises ValueError: If an impossible CBF mode is selected.

    :return: targets to observe
    """
    if alt_limit is None:
        alt_limit = Quantity(30, u.deg)

    if mode == "VIS":
        coord_table_path = resources.files(data) / "calibrators.csv"
    elif mode == "PST":
        coord_table_path = resources.files(data) / "pulsar_bright.csv"
    else:
        msg = f"`mode` must be either 'VIS' or 'PST' (got '{mode}')"
        raise ValueError(msg)

    with resources.as_file(coord_table_path) as path:
        coord_table = Table.read(path)
    coord_table["coords"] = SkyCoord(
        ra=coord_table["ra_deg"] * u.deg, dec=coord_table["dec_deg"] * u.deg
    )
    coord_table["index"] = np.arange(len(coord_table))
    coord_table.add_index("index")

    # First pick targets that are up
    location = EarthLocation.of_site("SKA-Low")
    if obs_time is None:
        obs_time = Time.now()
    altitudes = coord_table["coords"].transform_to(AltAz(obstime=obs_time, location=location)).alt
    alt_idx = altitudes > alt_limit

    # Check solar separation
    obs_freq_mhz = coarse_channel_to_freq(
        coarse_channel=coarse_channel_start,
    )
    beam_size = station_beam_size(
        obs_freq=obs_freq_mhz * u.MHz,
    )
    sun_gcrs = get_sun(obs_time)
    # Explicitly transform to AltAz to avoid issues with coordinate frame
    sun_altaz = sun_gcrs.transform_to(AltAz(obstime=obs_time, location=location))
    coords_altaz = coord_table["coords"].transform_to(AltAz(obstime=obs_time, location=location))
    sun_seps = coords_altaz.separation(sun_altaz)
    sun_idx = sun_seps > (2 * beam_size)

    good_idx = alt_idx & sun_idx

    # Nothing to observe
    if good_idx.sum() == 0:
        return Targets(None, None)

    up_table = coord_table[good_idx]

    # Now pick the brightest calibrator as 'primary'
    primary_idx = np.argmax(up_table["s_197"])
    primary = up_table.iloc[primary_idx]

    if good_idx.sum() == 1:
        return Targets(primary, None)

    remaining = up_table[np.arange(len(up_table)) != primary_idx]

    return Targets(
        primary=primary,
        secondary=remaining,
    )
