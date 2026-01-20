# pylint: disable=no-member
from astropy import units as u
from ska_oso_pdm import TelescopeType, ValidationArrayAssembly

from ska_oso_services.validation import (
    get_low_basic_capability_parameter_from_osd,
    get_subarray_specific_parameter_from_osd,
)

MID_CHANNEL_WIDTH = (
    get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_MID,
        ValidationArrayAssembly.AA05,
        "allowed_channel_width_values_hz",
    )[0] # we're only supporting continuum right now, so we only need this number
    * u.Hz
)


LOW_MINIMUM_FREQUENCY = get_low_basic_capability_parameter_from_osd("min_frequency_hz") * u.Hz
LOW_MAXIMUM_FREQUENCY = get_low_basic_capability_parameter_from_osd("max_frequency_hz") * u.Hz
LOW_STATION_CHANNEL_WIDTH = (
    get_low_basic_capability_parameter_from_osd("coarse_channel_width_hz") * u.Hz
)

LOW_CHANNEL_BLOCK = 8 * LOW_STATION_CHANNEL_WIDTH  # = 6.25 MHz
LOW_CONTINUUM_CHANNEL_WIDTH = (
    LOW_STATION_CHANNEL_WIDTH
    / get_low_basic_capability_parameter_from_osd("number_continuum_channels_per_coarse_channel")
)

LOW_PST_CHANNEL_WIDTH = (16 * LOW_STATION_CHANNEL_WIDTH) / 3456
STEP_SECONDS_DEFAULT_VISIBILITY = 10
# palette
T10_COLOURS = {
    "blue": "#1A29B3",
    "teal": "#76B7B2",
    "gold": "#EDC948",
    "red": "#CA380B",
}

MID_DISH_DIAMETER = 15 * u.m
LOW_STATION_DIAMETER = 39 * u.m

# CSP constants taken from the CSP source code.
# Common sample rate for all receptor data streams,
# achieved after Resampling & Delay Tracking  (RDT) [Hz];
# applies for all function modes except VLBI
COMMON_SAMPLE_RATE = 220200960 * u.Hz
VCC_OVERSAMPLING_FACTOR = 10 / 9
MID_FREQUENCY_SLICE_BANDWIDTH = COMMON_SAMPLE_RATE / VCC_OVERSAMPLING_FACTOR
