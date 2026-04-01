import astropy.units as u

from ska_oso_services.validation.constraints import calculate_altitude_from_hourangle
from ska_oso_pdm import TelescopeType

from tests.unit.validation import FAKE_TARGET_AT_LOW_ZENTIH

def test_calculate_altitude_from_hourangle_returns_correct_value():
    """
    a target with a declination equal to the latitude of the observatory will have an altitude
    of 90 degrees (i.e. will be directly overhead) at a hourangle of zero
    """
    low_altitude = calculate_altitude_from_hourangle(
        TelescopeType.SKA_LOW,
        FAKE_TARGET_AT_LOW_ZENTIH,
        u.Quantity(0.0, "hourangle")
    )

    mid_altitude = calculate_altitude_from_hourangle(
        TelescopeType.SKA_MID,
        FAKE_TARGET_AT_LOW_ZENTIH,
        u.Quantity(0.0, "hourangle")
    )

    assert low_altitude == u.Quantity(90.0, "degree")
    assert mid_altitude != u.Quantity(90.0, "degree")