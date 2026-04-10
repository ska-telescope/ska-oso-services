# pylint: disable=no-member
import pytest
from astropy import units as u
from astropy.units import Quantity

from ska_oso_services.common import astro


@pytest.fixture(name="mock_low_station_channel_width", autouse=False)
def fixture_low_station_channel_width(monkeypatch):
    monkeypatch.setattr(astro, "low_station_channel_width", lambda: 0.78125 * 1e6 * u.Hz)


def test_low_coarse_channel_to_frequency_returns_expected_value_and_unit():
    result = astro.low_coarse_channel_to_frequency(96)

    assert isinstance(result, Quantity)
    assert result.unit == u.Hz
    assert result.value == 75e6


def test_low_frequency_to_coarse_channel_returns_expected_value_and_unit():
    result = astro.low_frequency_to_coarse_channel(Quantity(56.25, u.MHz))

    assert result == 72


def test_low_coarse_channel_start_to_centre_frequency_returns_expected_value_and_unit():
    result = astro.low_coarse_channel_start_to_centre_frequency(88, 10)

    assert isinstance(result, Quantity)
    assert result.unit == u.Hz
    assert result.value == 72265625


def test_low_centre_frequency_to_coarse_channel_start_returns_expected_type_and_value():
    result = astro.low_centre_frequency_to_coarse_channel_start(104.296875 * u.MHz, 10)

    assert result.is_integer()
    assert result == 129


def test_low_centre_frequency_to_coarse_channel_end_returns_expected_type_and_value():
    result = astro.low_centre_frequency_to_coarse_channel_end(104.296875 * u.MHz, 10)

    assert result.is_integer()
    assert result == 138


def test_low_centre_frequency_to_coarse_channel_start_and_end_is_consistent():
    bandwidth_channels = 20
    start = astro.low_centre_frequency_to_coarse_channel_start(
        104.296875 * u.MHz, bandwidth_channels
    )
    end = astro.low_centre_frequency_to_coarse_channel_end(104.296875 * u.MHz, bandwidth_channels)

    assert (end - start) == (
        bandwidth_channels - 1
    )  # minus 1 as the channel number defines the start of the channel
