"""
Frequency sweep SBDefinition generation with a dynamic number of scans (based
on the requested start channel and bandwidth), each using a different CSP Configuration.

This is a Low Commissioning use case and an example of SBDefinition generation
from parameters other than a Proposal ScienceProgramme. Eventually we expect the inputs
to this to evolve into more standard observatory use cases.
"""

# pylint: disable=no-member
from datetime import timedelta

import astropy.units as u
import numpy as np
from ska_oso_pdm import (
    Beam,
    PythonArguments,
    SBDefinition,
    Target,
    TiedArrayBeams,
    ValidationArrayAssembly,
)
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MCCSAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id as generate_csp_configuration_id
from ska_oso_pdm.builders.utils import scan_definition_id
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition, SDPConfiguration, SDPScript
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation

from ska_oso_services.common.astro import low_coarse_channel_start_to_centre_frequency


def generate_frequency_sweep(
    target: Target,
    target_dwell: timedelta,
    coarse_channel_start: int,
    coarse_channel_end: int,
    coarse_channel_bandwidth: int,
    pst_mode: bool,
    stations: list[int],
) -> SBDefinition:
    """
    Generate a frequency sweep SBDefinition.

    Builds a Low SBDefinition with one target and one scan per frequency step.
    """
    sbd = LowSBDefinitionBuilder(
        name=f"FreqSweep {target.name}; "
        f"CC {coarse_channel_start} - {coarse_channel_end}; BW {coarse_channel_bandwidth}",
        mccs_allocation=MCCSAllocationBuilder(stations=stations),
        targets=[target],
        csp_configurations=[],
        sdp_configurations=[
            SDPConfiguration(
                sdp_script=SDPScript.VIS_RECEIVE, script_version="latest", script_parameters={}
            )
        ],
        validate_against=ValidationArrayAssembly.AA1,
    )
    # Remove subarray_id arg that the builder adds - probably should be removed from the builder
    sbd.activities["observe"].function_args["init"] = PythonArguments()

    coarse_channel_span = coarse_channel_end - coarse_channel_start
    n_scans, remainder = divmod(coarse_channel_span, coarse_channel_bandwidth)

    if remainder != 0:
        n_scans += 1
        scan_starts = np.linspace(
            coarse_channel_start, coarse_channel_end - coarse_channel_bandwidth, n_scans
        )
    else:
        scan_starts = np.arange(
            coarse_channel_start,
            coarse_channel_end,
            coarse_channel_bandwidth,
            dtype=float,
        )

    scan_starts = np.round(scan_starts).astype(int)

    if pst_mode:
        pst_beams = [
            Beam(
                beam_id=1,
                beam_name=target.name,
                beam_coordinate=target.reference_coordinate,
                stn_weights=[1.0] * len(sbd.mccs_allocation.subarray_beams[0].apertures),
            )
        ]
        target.tied_array_beams = TiedArrayBeams(pst_beams=pst_beams)

    for index, scan_start in enumerate(scan_starts):
        csp_configuration = CSPConfiguration(
            config_id=generate_csp_configuration_id(),
            name=f"Scan {index} Config",
            lowcbf=LowCBFConfiguration(
                do_pst=pst_mode,
                correlation_spws=[
                    Correlation(
                        spw_id=1,
                        number_of_channels=int(coarse_channel_bandwidth),
                        centre_frequency=low_coarse_channel_start_to_centre_frequency(
                            scan_start, coarse_channel_bandwidth
                        )
                        .to(u.Hz)
                        .value,
                        integration_time_ms=849,
                        logical_fsp_ids=[],
                        zoom_factor=0,
                    )
                ],
            ),
        )

        sbd.csp_configurations.append(csp_configuration)  # pylint: disable=no-member

        _add_scan_for_csp_configuration(sbd, csp_configuration, target_dwell)

    return sbd


def _add_scan_for_csp_configuration(
    sbd: SBDefinition, csp_configuration: CSPConfiguration, duration: timedelta
) -> SBDefinition:
    # Assume one Target that we use for every scan
    target = sbd.targets[0]

    scan = ScanDefinition(
        scan_definition_id=scan_definition_id(),
        scan_intent="Science",
        target_ref=target.target_id,
        csp_configuration_ref=csp_configuration.config_id,
        scan_duration_ms=duration,
    )

    sbd.mccs_allocation.subarray_beams[0].scan_sequence.append(scan)
    return sbd
