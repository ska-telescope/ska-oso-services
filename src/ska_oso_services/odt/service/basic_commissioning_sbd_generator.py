# pylint: disable=no-member
from datetime import timedelta

import astropy.units as u
from ska_oso_pdm import Beam, SBDefinition, Target, TiedArrayBeams
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MCCSAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id, scan_definition_id
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation

from ska_oso_services.common.astro import low_coarse_channel_start_to_centre_frequency


def generate_basic_commissioning_sbd(
    name: str | None,
    target: Target,
    duration: timedelta,
    coarse_channel_start: int,
    coarse_channel_bandwidth: int,
    pst_mode: bool,
    stations: list[int],
) -> SBDefinition:
    """
    Create a basic commissioning Scheduling Block Definition with a single scan
    on the given target and CSP set up.

    If pst_mode is True then a single on-axis PST beam will be added to the scan.

    Note this doesn't create an SDPConfiguration in the SBD for any SDP scripts.
    In this case ska-oso-scripting
    will create default scripts using the latest script parameters.
    To customise this, add an SDPConfiguration
    to the result of this function
    """

    if name is None:
        name = (
            f"Commissioning - {target.name} "
            f"Channel start {coarse_channel_start} BW {coarse_channel_bandwidth}"
        )
    sbd: SBDefinition = LowSBDefinitionBuilder(
        metadata=None,
        mccs_allocation=MCCSAllocationBuilder(stations=stations),
        targets=[target],
        csp_configurations=[],
    )

    # Then the CSP Configuration
    csp_configuration = CSPConfiguration(
        config_id=csp_configuration_id(),
        name=f"{name} CSPConfiguration",
        lowcbf=LowCBFConfiguration(
            do_pst=False,
            correlation_spws=[
                Correlation(
                    spw_id=1,
                    number_of_channels=coarse_channel_bandwidth,
                    centre_frequency=low_coarse_channel_start_to_centre_frequency(
                        coarse_channel_start, coarse_channel_bandwidth
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

    # Then add PST if needed
    if pst_mode:
        # Add a single on axis beam using the main Target info
        csp_configuration.lowcbf.do_pst = True
        target.tied_array_beams = TiedArrayBeams(
            pst_beams=[
                Beam(
                    beam_id=1,
                    beam_name=f"{target.name}_PST",
                    beam_coordinate=target.reference_coordinate,
                    stn_weights=[1.0] * len(stations),
                )
            ]
        )

    # Finally bring it all together for this observation in a scan
    scan = ScanDefinition(
        scan_definition_id=scan_definition_id(),
        target_ref=target.target_id,
        csp_configuration_ref=csp_configuration.config_id,
        scan_duration_ms=duration,
    )

    sbd.mccs_allocation.subarray_beams[0].scan_sequence.append(scan)

    return sbd
