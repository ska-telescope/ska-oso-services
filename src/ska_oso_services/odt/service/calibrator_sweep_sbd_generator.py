"""
Calibrator sweep SBDefinition generation with a dynamic number of scans (based
on the requested total duration and scan time) of targets that are visible
at the expected start time.

This is a Low Commissioning use case and the first examples of SBDefinition generation
from parameters other than a Proposal ScienceProgramme. Eventually we expect the inputs
to this to evolve into more standard observatory use cases.

The expected start time and picking of targets based on that is more of a scheduler task
and will eventually be removed, but this is what is needed during commissioning currently.
"""

# pylint: disable=no-member
import logging
from datetime import timedelta

import astropy.units as u
from astropy.table import Row
from astropy.time import Time
from ska_oso_pdm import (
    Beam,
    ICRSCoordinates,
    PythonArguments,
    SBDefinition,
    Target,
    TiedArrayBeams,
    ValidationArrayAssembly,
)
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MCCSAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id, scan_definition_id, target_id
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition, SDPConfiguration, SDPScript
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation

from ska_oso_services.common.astro import low_coarse_channel_start_to_centre_frequency
from ska_oso_services.odt.service.commissioning.generation_utils import pick_targets

LOGGER = logging.getLogger(__name__)


def generate_cal_sweep_sbd(
    obs_start: Time,
    duration: timedelta,
    primary_dwell: timedelta,
    secondary_dwell: timedelta | None,
    interleave_primary: bool,
    coarse_channel_start: int,
    coarse_channel_bandwidth: int,
    pst_mode: bool,
    stations: list[int],
) -> SBDefinition:
    """
    Generate a calibrator sweep SBDefinition.

    Builds a Low SBDefinition with a single CSP configuration and single subarray beam
    and a scan. Targets are chosen by what is visible at the start time and are added to
    the scan sequence for the subarray beam
    """
    sbd = LowSBDefinitionBuilder(
        name=f"CalSweep {obs_start}",
        mccs_allocation=MCCSAllocationBuilder(stations=stations),
        targets=[],
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

    csp_configuration = CSPConfiguration(
        config_id=csp_configuration_id(),
        name=f"Channel start {coarse_channel_start} BW {coarse_channel_bandwidth}",
        lowcbf=LowCBFConfiguration(
            do_pst=pst_mode,
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

    sbd.csp_configurations.append(csp_configuration)

    pick_targets_and_add_scans(
        sbd=sbd,
        start_time=obs_start,
        duration=duration,
        primary_dwell=primary_dwell,
        secondary_dwell=secondary_dwell,
        interleave_primary=interleave_primary,
        pst_mode=pst_mode,
        coarse_channel_start=coarse_channel_start,
    )

    return sbd


def pick_targets_and_add_scans(
    sbd: SBDefinition,
    start_time: Time,
    duration: timedelta,
    primary_dwell: timedelta,
    secondary_dwell: timedelta | None,
    interleave_primary: bool,
    pst_mode: bool,
    coarse_channel_start: int,
) -> SBDefinition:
    """
    Fill an SBDefinition's scan sequence with calibrator/pulsar targets
    and returns the mutated SBD

    Iterates from *start_time* until the (*duration*) is met.
    At each step the brightest currently-visible target is chosen
    as the primary, with dimmer visible targets used as secondaries.
    """
    end_time = Time(start_time + duration)

    num_stations = len(sbd.mccs_allocation.subarray_beams[0].apertures)
    while True:
        total_sbd_time = total_scans_time_for_sbd(sbd)
        # Check if after all the scans that are built up so far,
        # there is enough time for at least one more
        current_expected_end_time = start_time + total_sbd_time

        if (current_expected_end_time + primary_dwell) > end_time:
            return sbd

        targets = pick_targets(
            coarse_channel_start=coarse_channel_start,
            mode="PST" if pst_mode else "VIS",
            obs_time=current_expected_end_time,
        )

        if targets.primary is None:
            LOGGER.debug(
                "No more targets available. SBD will run for %s",
                total_sbd_time,
            )
            return sbd

        primary_target = pdm_target_from_aiv_target(targets.primary, pst_mode, num_stations)
        sbd.targets.append(primary_target)

        _add_scan_for_target(sbd=sbd, target=primary_target, duration=primary_dwell)
        total_sbd_time += primary_dwell

        if secondary_dwell is None:
            continue

        for secondary in targets.secondary or []:
            if (total_sbd_time + secondary_dwell) > duration:
                return sbd

            secondary_target = pdm_target_from_aiv_target(secondary, pst_mode, num_stations)
            sbd.targets.append(secondary_target)
            _add_scan_for_target(sbd=sbd, target=secondary_target, duration=secondary_dwell)
            total_sbd_time += secondary_dwell

            if interleave_primary:
                if (total_sbd_time + primary_dwell) > duration:
                    return sbd
                _add_scan_for_target(sbd=sbd, target=primary_target, duration=primary_dwell)
                total_sbd_time += primary_dwell


def _add_scan_for_target(sbd: SBDefinition, target: Target, duration: timedelta) -> SBDefinition:
    csp_configuration = sbd.csp_configurations[0]

    scan = ScanDefinition(
        scan_definition_id=scan_definition_id(),
        scan_intent="Science",
        target_ref=target.target_id,
        csp_configuration_ref=csp_configuration.config_id,
        scan_duration_ms=duration,
    )

    sbd.mccs_allocation.subarray_beams[0].scan_sequence.append(scan)
    return sbd


def pdm_target_from_aiv_target(
    aiv_target: Row, pst_mode: bool, num_stations: int | None = None
) -> Target:
    """
    Convert an astropy table row from the AIV catalogue to a PDM
    :class:`Target`.

    :return: A PDM Target with ICRS coordinates.
    """

    reference_coordinate = ICRSCoordinates(
        ra_str=aiv_target["coords"].ra.to_string(u.hour, sep=":"),
        dec_str=aiv_target["coords"].dec.to_string(u.degree, sep=":"),
    )

    if pst_mode:
        if num_stations is None:
            raise ValueError("num_stations must also be given to create a pst_beam")
        pst_beams = [
            Beam(
                beam_id=1,
                beam_name=aiv_target["name"],
                beam_coordinate=reference_coordinate,
                stn_weights=[1.0] * num_stations,
            )
        ]
    else:
        pst_beams = []

    return Target(
        target_id=target_id(),
        name=aiv_target["name"],
        reference_coordinate=reference_coordinate,
        tied_array_beams=TiedArrayBeams(pst_beams=pst_beams),
    )


def total_scans_time_for_sbd(sbd: SBDefinition) -> timedelta:
    return timedelta(
        seconds=sum(
            scan.scan_duration_ms.seconds
            for scan in sbd.mccs_allocation.subarray_beams[0].scan_sequence
        )
    )
