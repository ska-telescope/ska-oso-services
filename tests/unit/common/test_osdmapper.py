import pytest
from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand

from ska_oso_services.common.osdmapper import (
    Band5bSubband,
    CbfMetrics,
    Constraints,
    LowQualityAttributeMetrics,
    MidFrequencyBand,
    configuration_from_osd,
    get_low_basic_capability_parameter_from_osd,
    get_mid_frequency_band_data_from_osd,
    get_subarray_specific_parameter_from_osd,
    get_telescope_observing_constraint,
)


def test_get_basic_low_capabilities_function_passes_for_valid_parameter():
    value = get_low_basic_capability_parameter_from_osd("coarse_channel_width_hz")
    assert value is not None


def test_get_basic_low_capabilities_function_fails_for_invalid_parameter():
    with pytest.raises(ValueError):
        get_low_basic_capability_parameter_from_osd("invalid_parameter")


def test_get_mid_frequency_band_data_from_osd_passes_for_valid_band():
    value = get_mid_frequency_band_data_from_osd(ReceiverBand.BAND_1)
    assert type(value) is MidFrequencyBand
    assert value.rx_id == "Band_1"


def test_get_mid_frequency_band_data_from_osd_passes_for_band5b():
    value = get_mid_frequency_band_data_from_osd(
        ReceiverBand.BAND_5B, pdm_Band5bSubband.BAND5B_SUBBAND2
    )
    assert type(value) is Band5bSubband
    assert value.sub_band == 2


def test_get_subarray_specific_parameters_fails_for_invalid_telescope():
    with pytest.raises(ValueError):
        get_subarray_specific_parameter_from_osd(
            TelescopeType.MEERKAT, SubArrayMID.AA1_ALL, "blah"
        )


def test_get_subarray_specific_parameter_passes_with_mid_subarray_value():
    value = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_MID, SubArrayMID.AA1_ALL, "number_pst_beams"
    )
    assert value is not None


def test_get_subarray_specific_parameter_fails_with_invalid_mid_subarray_value():
    with pytest.raises(ValueError):
        get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_MID, SubArrayMID.AA4_SKA_ONLY, "number_pst_beams"
        )


def test_get_subarray_specific_parameter_fails_for_invalid_parameter():
    with pytest.raises(ValueError):
        get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_LOW, SubArrayLOW.AA2_ALL, "not a parameter"
        )


def test_get_subarray_specific_parameter_passes_for_valid_inputs():
    value = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_LOW, SubArrayLOW.AA2_ALL, "number_pst_beams"
    )
    assert value == 4


def test_configuration_from_osd_returns_constraints():
    value = configuration_from_osd()
    assert type(value.ska_low.constraints) is Constraints
    assert type(value.ska_mid.constraints) is Constraints


def test_get_telescope_observing_constraint_returns_constraints():
    value = get_telescope_observing_constraint(
        TelescopeType.SKA_MID, "jupiter_avoidance_angle_deg"
    )
    assert value == 10.0


def test_get_telescope_observing_constraint_returns_constraints_for_low():
    value = get_telescope_observing_constraint(TelescopeType.SKA_LOW, "sun_avoidance_angle_deg")
    assert value == 30.0


def test_get_telescope_observing_constraint_fails_for_invalid_parameter():
    with pytest.raises(ValueError):
        get_telescope_observing_constraint(TelescopeType.SKA_LOW, "not_a_parameter")


def test_configuration_from_osd_returns_low_cbf_metrics():
    value = configuration_from_osd()
    assert type(value.ska_low.quality_attribute_metrics) is LowQualityAttributeMetrics
    assert type(value.ska_low.quality_attribute_metrics.cbf) is CbfMetrics
    cbf = value.ska_low.quality_attribute_metrics.cbf
    assert (
        cbf.alveo_configured_percent is not None or cbf.processors_ready_percent is not None
    ), "At least one of alveo_configured_percent or processors_ready_percent must be present"
