from ska_oso_pdm import ValidationArrayAssembly
from ska_oso_pdm.sb_definition import CSPConfiguration
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand

from ska_oso_services.validation.csp import validate_csp
from ska_oso_services.validation.model import ValidationContext

band_5b_json = """
{
      "config_id": "csp-configuration-12754",
      "name": "my csp config",
      "midcbf": {
        "frequency_band": "5b",
        "band5b_subband": 1,
        "subbands": [
          {
            "frequency_slice_offset": {
              "value": 0,
              "unit": "MHz"
            },
            "correlation_spws": [
              {
                "spw_id": 1,
                "logical_fsp_ids": [],
                "zoom_factor": 0,
                "centre_frequency": 11961280000.0,
                "number_of_channels": 18600,
                "channel_averaging_factor": 1,
                "time_integration_factor": 1
              }
            ]
          }
        ]
      }
    }
"""


def test_mid_csp_configuration_throws_central_frequency_error(mid_sbd_builder):
    """
    currently the Mid CSPBuilder sets the incorrect band for the
    CSP set up. This means the central frequency is incorrect for the
    set-up and so 2 errors should be triggered, one for the central frequency
    and one for the combined central frequency and bandwidth validation
    """
    sbd = mid_sbd_builder
    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert len(result) == 2
    assert (
        result[0].message
        == "Centre frequency of spectral window 450007040.0 Hz is outside of Band_2"
    )
    assert result[1].message == "Spectral window is outside allowed range"


def test_mid_telescope_csp_configuration_passes_for_valid_setup(mid_sbd_builder):
    sbd = mid_sbd_builder
    sbd.csp_configurations[0].midcbf.frequency_band = ReceiverBand.BAND_1

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_mid_telescope_csp_configuration_passes_for_valid_setup_band_5b_edition(
    mid_sbd_builder,
):
    sbd = mid_sbd_builder

    sbd.csp_configurations[0] = CSPConfiguration.model_validate_json(band_5b_json)

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_mid_telescope_csp_configuration_throws_window_error(mid_sbd_builder):
    """
    This test has a valid central frequency and bandwidth, but the combination
    puts the window outside the band.
    """
    mid_sbd = mid_sbd_builder
    mid_sbd.csp_configurations[0].midcbf.frequency_band = ReceiverBand.BAND_1
    mid_sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws[0].number_of_channels = 20000

    input_context = ValidationContext(
        primary_entity=mid_sbd.csp_configurations[0],
        telescope=mid_sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result[0].message == "Spectral window is outside allowed range"


def test_mid_telescope_csp_configuration_throws_bandwidth_error(mid_sbd_builder):
    mid_sbd = mid_sbd_builder
    mid_sbd.csp_configurations[0].midcbf.frequency_band = ReceiverBand.BAND_1
    mid_sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws[
        0
    ].number_of_channels = 100000

    input_context = ValidationContext(
        primary_entity=mid_sbd.csp_configurations[0],
        telescope=mid_sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message == "Bandwidth of spectral window 1344.0 MHz is outside of available "
        "bandwidth 800.0 MHz for ska_mid AA1"
    )


def test_mid_telescope_csp_configuration_throws_fsp_error(mid_sbd_builder):
    sbd = mid_sbd_builder

    sbd.csp_configurations[0].midcbf.frequency_band = ReceiverBand.BAND_1

    correlation_spw = sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws[0]
    correlation_spws = [correlation_spw for _ in range(5)]
    sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws = correlation_spws

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message
        == "Number of FSPs required for CSP configuration is greater than the 8 FSPs "
        "available for array assembly AA1"
    )


def test_low_telescope_csp_configuration_passes_for_valid_setup(low_sbd_builder):
    low_sbd = low_sbd_builder
    input_context = ValidationContext(
        primary_entity=low_sbd.csp_configurations[0],
        telescope=low_sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_low_telescope_csp_configuration_throws_central_frequency_error(low_sbd_builder):
    low_sbd = low_sbd_builder
    low_sbd.csp_configurations[0].lowcbf.correlation_spws[0].centre_frequency = 100

    input_context = ValidationContext(
        primary_entity=low_sbd.csp_configurations[0],
        telescope=low_sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message
        == "Centre frequency of spectral window 100.0 Hz is outside of the telescope capabilities"
    )
    assert result[1].message == "Spectral window is outside allowed range"


def test_low_telescope_throw_bandwidth_error(low_sbd_builder):
    low_sbd = low_sbd_builder
    low_sbd.csp_configurations[0].lowcbf.correlation_spws[0].number_of_channels = 100
    input_context = ValidationContext(
        primary_entity=low_sbd.csp_configurations[0],
        telescope=low_sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message
        == "Bandwidth of spectral window 78.125 MHz is outside of available bandwidth "
        "75.0 MHz for ska_low AA1"
    )
