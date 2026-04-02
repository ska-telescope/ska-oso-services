from astropy.units import Quantity

from ska_oso_services.common.static.constants import low_station_channel_width


def low_coarse_channel_start_to_centre_frequency(
    coarse_channel_start: int, coarse_channel_bandwidth: int
) -> Quantity:
    return low_station_channel_width() * (
        coarse_channel_start + (coarse_channel_bandwidth) / 2 - 0.5
    )


def low_centre_frequency_to_coarse_channel_start(
    centre_frequency: Quantity, coarse_channel_bandwidth: int
) -> int:
    return centre_frequency / low_station_channel_width() - (coarse_channel_bandwidth / 2 - 0.5)


def low_centre_frequency_to_coarse_channel_end(
    centre_frequency: Quantity, coarse_channel_bandwidth: int
) -> int:
    return centre_frequency / low_station_channel_width() + (coarse_channel_bandwidth / 2 - 0.5)
