from ska_oso_services.common.osdmapper import Configuration, FrequencyBand
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
    assert response.ska_low.frequency_band == FrequencyBand(
        min_frequency_hz=50e6, max_frequency_hz=350e6
    )
    assert len(response.ska_mid.frequency_band) == 6
    assert len(response.ska_mid.subarrays) == 4
    assert len(response.ska_low.subarrays) == 5
    assert len(response.ska_mid.frequency_band[-1].band5b_subbands) == 3
