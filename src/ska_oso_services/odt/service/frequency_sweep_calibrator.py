"""
Frequency sweep SBDefinition generation.

This module provides generation of an SBDefinition for the Low Commissioning
frequency sweep use case.
"""

from datetime import timedelta

import numpy as np
from ska_oso_pdm import SBDefinition, Target
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MCCSAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id as generate_csp_configuration_id
from ska_oso_pdm.builders.utils import scan_definition_id
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation

CHANNEL_WIDTH_HZ = 781.25e3


def generate_frequency_sweep(
    target: Target,
    target_dwell: timedelta,
    coarse_channel_start: int,
    coarse_channel_end: int,
    coarse_channel_bandwidth: int,
    mode: str = "VIS",
    stations: list[str] | None = None,
) -> SBDefinition:
    """
    Generate a frequency sweep SBDefinition.

    Builds a Low SBDefinition with one target and one scan per frequency step.
    """
    mccs_allocation = (
        MCCSAllocationBuilder() if stations is None else MCCSAllocationBuilder(stations=stations)
    )
    sbd = LowSBDefinitionBuilder(
        mccs_allocation=mccs_allocation,
        targets=[target],
        csp_configurations=[],
    )

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

    for index, scan_start in enumerate(scan_starts):
        csp_configuration = CSPConfiguration(
            config_id=generate_csp_configuration_id(),
            name=f"Scan {index} Config",
            lowcbf=LowCBFConfiguration(
                do_pst=mode.upper() == "PST",
                correlation_spws=[
                    Correlation(
                        spw_id=1,
                        number_of_channels=int(coarse_channel_bandwidth),
                        centre_frequency=CHANNEL_WIDTH_HZ
                        * (int(scan_start) + 0.5 * int(coarse_channel_bandwidth) - 0.5),
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
        target_ref=target.target_id,
        csp_configuration_ref=csp_configuration.config_id,
        scan_duration_ms=duration,
    )

    sbd.mccs_allocation.subarray_beams[0].scan_sequence.append(scan)
    return sbd


def total_scans_time_for_sbd_with_software_slew(sbd: SBDefinition) -> timedelta:
    return timedelta(
        seconds=sum(
            scan.scan_duration_ms.seconds
            for scan in sbd.mccs_allocation.subarray_beams[0].scan_sequence
        )
    )
