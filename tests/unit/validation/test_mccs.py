from astropy import units as u
from ska_oso_pdm import ValidationArrayAssembly
from ska_oso_pdm._shared import TiedArrayBeams
from ska_oso_pdm.builders import LowSBDefinitionBuilder, populate_scan_sequences
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import SubarrayBeamConfiguration

from ska_oso_services.validation.mccs import validate_mccs
from ska_oso_services.validation.model import ValidationContext

pst_beam_json = """
{
        "pst_beams":
        [
          {
            "beam_id": 99005,
            "beam_name": "1E0102-72.3",
            "beam_coordinate": {
              "kind": "icrs",
              "ra_str": "01:04:01.2000",
              "dec_str": "-72:01:52.320"
              }
          },
          {
            "beam_id": 93680,
            "beam_name": "SMC X-1",
            "beam_coordinate": {
              "kind": "icrs",
              "ra_str": "01:17:05.1457",
              "dec_str": "-73:26:36.015"
            }
          }
        ]
}
"""

substation_json = """
{
        "apertures": [
          {
            "station_id": 345,
            "substation_id": 1,
            "weighting_key": "uniform"
          },
          {
            "station_id": 350,
            "substation_id": 1,
            "weighting_key": "uniform"
          },
          {
            "station_id": 350,
            "substation_id": 2,
            "weighting_key": "uniform"
          },
          {
            "station_id": 352,
            "substation_id": 1,
            "weighting_key": "uniform"
          },
          {
            "station_id": 431,
            "substation_id": 1,
            "weighting_key": "uniform"
          }
        ],
        "subarray_beam_id": 1,
        "scan_sequence": [
          {
            "scan_definition_id": "scan-definition-19684",
            "scan_duration_ms": 600000,
            "target_ref": "target-87983",
            "csp_configuration_ref": "csp-configuration-86456",
            "scan_intent": "Science",
            "pointing_correction": "MAINTAIN"
          }
        ]
      }
"""


def test_validate_mccs_passes_for_simple_mccs_allocation():
    sbd = LowSBDefinitionBuilder()
    sbd = populate_scan_sequences(sbd, [6000000])

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA05,
    )

    result = validate_mccs(input_context)
    assert result == []


def test_validate_mccs_fails_for_multiple_pst_beams_for_aa05_and_passes_for_aa2():
    sbd = LowSBDefinitionBuilder()
    sbd = populate_scan_sequences(sbd, [6000000])

    sbd.targets[0].tied_array_beams = TiedArrayBeams.model_validate_json(pst_beam_json)

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA05,
    )

    result = validate_mccs(input_context)
    assert len(result) == 1
    assert result[0].message == "Number of PST beams, 2, for scan 1 exceeds allowed 1 for AA0.5"

    input_context.array_assembly = ValidationArrayAssembly.AA2
    result = validate_mccs(input_context)
    assert result == []


def test_validate_number_substations():
    sbd = LowSBDefinitionBuilder()

    # building an SBD for the test - bit hacky
    sbd.mccs_allocation.subarray_beams[0] = SubarrayBeamConfiguration.model_validate_json(
        substation_json
    )
    # making sure the csp_ref in the new scan matches that in the SBD
    sbd.mccs_allocation.subarray_beams[0].scan_sequence[0].csp_configuration_ref = (
        sbd.csp_configurations[0].config_id
    )
    # reducing the number of channels so as not to trigger the station bandwidth validation error
    sbd.csp_configurations[0].lowcbf.correlation_spws[0].number_of_channels = 30

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA05,
    )

    result = validate_mccs(input_context)
    assert len(result) == 1
    assert (
        result[0].message
        == "Maximum number of substations, 1, in subarray beam 1 exceeds allowed 0 for AA0.5"
    )

    input_context.array_assembly = ValidationArrayAssembly.AA1
    result = validate_mccs(input_context)

    assert result == []


def test_validate_mccs_fails_for_multiple_subarray_beams(low_multiple_subarray_beam):
    sbd = low_multiple_subarray_beam

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA05,
    )

    result = validate_mccs(input_context)

    assert len(result) == 1
    assert result[0].message == "Number of subarray beams, 2, exceeds allowed 1 for AA0.5"

    input_context.array_assembly = ValidationArrayAssembly.AA1
    result = validate_mccs(input_context)

    assert result == []


def test_validate_scan_durations(low_multiple_subarray_beam):
    sbd = low_multiple_subarray_beam
    sbd.mccs_allocation.subarray_beams[1].scan_sequence[0].scan_duration = 10 * u.s

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA1,
    )

    result = validate_mccs(input_context)

    assert len(result) == 1
    assert (
        result[0].message == "The scan durations for scan 1 are not equal for all subarray beams"
    )


def test_validate_station_bandwidth(
    low_multiple_subarray_beam_multiple_apertures_multiple_spws_with_pst,
):
    # this SBD has two science targets, one with PST beams, and a calibrator,
    # two subarray beams, one with multiple apertures and a CSP configuration
    # with multiple spectral windows. The total bandwidth for *each scan* of
    # all the spectral windows in the subarray beams does not exceed the available
    # bandwidth

    sbd = low_multiple_subarray_beam_multiple_apertures_multiple_spws_with_pst

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA2,
    )

    result = validate_mccs(input_context)
    assert len(result) == 0


def test_validate_station_bandwidth_fails_for_invalid_setup(
    low_multiple_subarray_beam_multiple_apertures_multiple_spws_with_pst,
):

    sbd = low_multiple_subarray_beam_multiple_apertures_multiple_spws_with_pst
    for spw in sbd.csp_configurations[1].lowcbf.correlation_spws:
        spw.number_of_channels = 96

    input_context = ValidationContext(
        primary_entity=sbd.mccs_allocation,
        relevant_context={"targets": sbd.targets, "csp_config": sbd.csp_configurations},
        telescope=sbd.telescope,
        array_assembly=ValidationArrayAssembly.AA2,
    )

    result = validate_mccs(input_context)
    assert len(result) == 2
    assert (
        result[0].message == "At least one station in scan 1 is using more bandwidth (918.75 MHz) "
        "than is available (150.0 MHz) for array assembly AA2"
    )
