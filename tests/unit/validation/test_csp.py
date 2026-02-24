from ska_oso_pdm import ValidationArrayAssembly
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MidSBDefinitionBuilder
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


def test_mid_telescope_csp_configuration_passes_for_valid_setup():
    sbd = MidSBDefinitionBuilder()
    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_mid_csp_configuration_throws_central_frequency_error():
    """
    currently the Mid CSPBuilder sets the incorrect band for the
    CSP set up. This means the central frequency is incorrect for the
    set-up and so 2 errors should be triggered, one for the central frequency
    and one for the combined central frequency and bandwidth validation
    """
    sbd = MidSBDefinitionBuilder()

    sbd.csp_configurations[0].midcbf.frequency_band = ReceiverBand.BAND_2

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert len(result) == 2
    assert (
        result[0].message
        == "Centre frequency of spectral window 1, 450007040.0 Hz, is outside of Band_2"
    )
    assert result[1].message == "Spectral window 1 is outside allowed range"


def test_mid_telescope_csp_configuration_passes_for_valid_setup_band_5b_edition():
    sbd = MidSBDefinitionBuilder()

    sbd.csp_configurations[0] = CSPConfiguration.model_validate_json(band_5b_json)

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_mid_telescope_csp_configuration_throws_window_error():
    """
    This test has a valid central frequency and bandwidth, but the combination
    puts the window outside the band.
    """
    sbd = MidSBDefinitionBuilder()
    sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws[0].number_of_channels = 20000

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result[0].message == "Spectral window 1 is outside allowed range"


def test_mid_telescope_csp_configuration_throws_bandwidth_error():
    sbd = MidSBDefinitionBuilder()
    sbd.csp_configurations[0].midcbf.subbands[0].correlation_spws[0].number_of_channels = 100000

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message == "Bandwidth of spectral window 1, 1344.0 MHz, is outside of available "
        "bandwidth 800.0 MHz for ska_mid AA1"
    )


def test_mid_telescope_csp_configuration_throws_fsp_error():
    sbd = MidSBDefinitionBuilder()

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
        == "Number of FSPs required for CSP configuration, 10, is greater than the 8 FSPs "
        "available for array assembly AA1"
    )


def test_low_telescope_csp_configuration_passes_for_valid_setup():
    sbd = LowSBDefinitionBuilder()
    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert result == []


def test_low_telescope_csp_configuration_throws_central_frequency_error():
    sbd = LowSBDefinitionBuilder()
    sbd.csp_configurations[0].lowcbf.correlation_spws[0].centre_frequency = 100

    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message
        == "Centre frequency of spectral window 1, 100.0 Hz, is outside of the telescope "
        "capabilities"
    )
    assert result[1].message == "Spectral window 1 is outside allowed range"


def test_low_telescope_throw_bandwidth_error():
    sbd = LowSBDefinitionBuilder()
    sbd.csp_configurations[0].lowcbf.correlation_spws[0].number_of_channels = 100
    input_context = ValidationContext(
        primary_entity=sbd.csp_configurations[0],
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_csp(input_context)
    assert (
        result[0].message
        == "Bandwidth of spectral window 1, 78.125 MHz, is outside of available bandwidth "
        "75.0 MHz for ska_low AA1"
    )
