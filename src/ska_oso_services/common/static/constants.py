# pylint: disable=no-member
from functools import cache

from astropy import units as u
from astropy.units import Quantity
from ska_oso_pdm import TelescopeType, ValidationArrayAssembly

from ska_oso_services.common.osdmapper import (
    get_low_basic_capability_parameter_from_osd,
    get_subarray_specific_parameter_from_osd,
)


@cache
def mid_channel_width() -> Quantity:
    """
    for both AA0.5 and AA1 this list has one element this is a list for AA2 and
    is something to do  with how MID is handling zoom windows. The MID and LOW
    OSD have diverged in this respect - we should probably address this before we
    support zooms
    """
    return (
        get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_MID,
            ValidationArrayAssembly.AA05,
            "allowed_channel_width_values_hz",
        )[0]
        * u.Hz
    )


@cache
def mid_frequency_slice_bandwidth() -> Quantity:
    """
    These are CSP constants taken from the CSP source code. Common sample rate for all
     receptor data streams, achieved after Resampling & Delay Tracking  (RDT) [Hz];
     applies for all function modes except VLBI
    """
    COMMON_SAMPLE_RATE = 220200960 * u.Hz
    VCC_OVERSAMPLING_FACTOR = 10 / 9
    return COMMON_SAMPLE_RATE / VCC_OVERSAMPLING_FACTOR


@cache
def low_minimum_frequency() -> Quantity:
    return get_low_basic_capability_parameter_from_osd("min_frequency_hz") * u.Hz


@cache
def low_maximum_frequency() -> Quantity:
    return get_low_basic_capability_parameter_from_osd("max_frequency_hz") * u.Hz


@cache
def low_station_channel_width() -> Quantity:
    return get_low_basic_capability_parameter_from_osd("coarse_channel_width_hz") * u.Hz


@cache
def low_continuum_channel_width() -> Quantity:
    return low_station_channel_width() / get_low_basic_capability_parameter_from_osd(
        "number_continuum_channels_per_coarse_channel"
    )


@cache
def low_pst_channel_width() -> Quantity:
    return 16 * low_station_channel_width() / 3456


MID_DISH_DIAMETER = Quantity(15, u.m)
LOW_STATION_DIAMETER = Quantity(39, u.m)


# Not telescope constants, used for visibility plots
STEP_SECONDS_DEFAULT_VISIBILITY = 10
# palette
T10_COLOURS = {
    "blue": "#1A29B3",
    "teal": "#76B7B2",
    "gold": "#EDC948",
    "red": "#CA380B",
}
