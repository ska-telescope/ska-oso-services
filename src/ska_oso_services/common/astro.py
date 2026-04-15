# pylint: disable=no-member
from astropy import units as u
from astropy.units import Quantity

from ska_oso_services.common.static.constants import low_station_channel_width


def low_coarse_channel_to_frequency(coarse_channel: int) -> Quantity:
    """Converts a number of coarse channels into the equivalent frequency"""
    return low_station_channel_width() * coarse_channel


def low_frequency_to_coarse_channel(frequency: Quantity) -> float:
    """This returns a float rather than an int as it can be used with
    channel start or centre frequencies. It is up to the caller to ensure which they are using."""
    return (frequency.to(u.Hz) / low_station_channel_width().to(u.Hz)).value


def low_coarse_channel_start_to_centre_frequency(
    coarse_channel_start: int, coarse_channel_bandwidth: int
) -> Quantity:
    return low_station_channel_width() * (
        coarse_channel_start + coarse_channel_bandwidth / 2 - 0.5
    )


def low_centre_frequency_to_coarse_channel_start(
    centre_frequency: Quantity, coarse_channel_bandwidth: int
) -> float:
    """
    This should be an integer channel number, but it is left up to the
    caller to ensure the validation of the inputs guarantees it is
    """
    return low_frequency_to_coarse_channel(centre_frequency) - (coarse_channel_bandwidth / 2 - 0.5)


def low_centre_frequency_to_coarse_channel_end(
    centre_frequency: Quantity, coarse_channel_bandwidth: int
) -> float:
    """
    This should be an integer channel number, but it is left up to
    the caller to ensure the validation of the inputs guarantees it is
    """
    return low_frequency_to_coarse_channel(centre_frequency) + (coarse_channel_bandwidth / 2 - 0.5)
