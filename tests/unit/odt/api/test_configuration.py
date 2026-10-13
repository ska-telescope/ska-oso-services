from unittest import mock

from ska_oso_services.common import itfmapper
from ska_oso_services.common.osdmapper import Configuration, LowFrequencyBand
from ska_oso_services.odt.api.configuration import configuration_get


def test_configuration_get():
    """
    This isn't really a unit test as it actually calls the OSD. Mocking out the
    OSD and returning the same data structure seems more effort than it is worth
    currently. As the OSD becomes better typed with the conversion to FastAPI
    as our use case expands, we can rethink these tests.
    """

    response = configuration_get()

    assert isinstance(response, Configuration)
    assert response.ska_low.frequency_band == LowFrequencyBand(
        min_frequency_hz=50e6,
        max_frequency_hz=350e6,
        min_coarse_channel=64,
        max_coarse_channel=447,
        coarse_channel_width_hz=781250.0,
        number_continuum_channels_per_coarse_channel=144,
        number_zoom_channels_per_coarse_channel=432,
        number_pst_channels_per_coarse_channel=216,
        number_pss_channels_per_coarse_channel=54,
    )
    assert len(response.ska_mid.frequency_band) == 6
    assert len(response.ska_mid.subarrays) == 4
    assert len(response.ska_low.subarrays) == 5
    assert [
        (subarray.name, [(station.id, station.label) for station in subarray.allowed_stations])
        for subarray in response.ska_low.itf_subarrays
    ] == [
        ("SKA-Low-ITF-CI", [(51, "ci5-1"), (52, "ci5-2")]),
        ("SKA-Low-ITF-EM", [(31, "em3-1"), (32, "em3-2"), (41, "em4-1"), (42, "em4-2")]),
    ]
    assert len(response.ska_mid.frequency_band[-1].band5b_subbands) == 3


def test_configuration_get_succeeds_when_itf_tmdata_is_unavailable():
    """
    The ITF subarrays are supplementary, so a failure to retrieve them should
    not affect the rest of the configuration.
    """
    itfmapper._CACHE.clear()
    with mock.patch.object(itfmapper, "TMData", side_effect=RuntimeError("unreachable")):
        response = configuration_get()
    itfmapper._CACHE.clear()

    assert response.ska_low.itf_subarrays == []
    assert len(response.ska_low.subarrays) == 5
    assert len(response.ska_mid.subarrays) == 4
