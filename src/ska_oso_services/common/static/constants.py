# pylint: disable=no-member
from astropy import units as u

MID_CHANNEL_WIDTH = 13.44 * u.kHz
LOW_STATION_CHANNEL_WIDTH = 0.78125 * u.MHz
LOW_CHANNEL_BLOCK = 8 * LOW_STATION_CHANNEL_WIDTH  # = 6.25 MHz
LOW_CONTINUUM_CHANNEL_WIDTH = (24 * LOW_STATION_CHANNEL_WIDTH) / 3456
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

# CSP constants taken from the CSP source code. Common sample rate for all receptor data streams,
# achieved after Resampling & Delay Tracking  (RDT) [Hz]; applies for all function
# modes except VLBI
COMMON_SAMPLE_RATE = 220200960 * u.Hz
VCC_OVERSAMPLING_FACTOR = 10 / 9
FREQUENCY_SLICE_BANDWIDTH = COMMON_SAMPLE_RATE / VCC_OVERSAMPLING_FACTOR
