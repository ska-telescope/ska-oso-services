import logging
from datetime import datetime, timedelta

import astropy.units as u
from astropy.table import Row
from astropy.time import Time
from ska_oso_pdm import ICRSCoordinates, SBDefinition, Target
from ska_oso_pdm.builders import LowSBDefinitionBuilder, MCCSAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id, scan_definition_id
from ska_oso_pdm.builders.utils import target_id as generate_target_id
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation

from ska_oso_services.odt.service.commissioning.script_utils import pick_targets

LOGGER = logging.getLogger(__name__)

CHANNEL_WIDTH_HZ = 781.25e3


def generate_cal_sweep_sbd(
    obs_start: Time,
    duration: timedelta,
    primary_dwell: timedelta,
    secondary_dwell: timedelta | None = None,
    interleave_primary: bool = False,
    coarse_channel_start: int = 206,
    coarse_channel_bandwidth: int = 96,
    with_pst: bool = False,
    stations: list[str] | None = None,
):

    # station_ids = [get_station_id(station_name) for station_name in station_names]

    sbd = LowSBDefinitionBuilder(
        mccs_allocation=MCCSAllocationBuilder(), targets=[], csp_configurations=[]
    )

    csp_configuration = CSPConfiguration(
        config_id=csp_configuration_id(),
        name="CalSweep CSPConfiguration",
        lowcbf=LowCBFConfiguration(
            do_pst=False,
            correlation_spws=[
                Correlation(
                    spw_id=1,
                    number_of_channels=coarse_channel_bandwidth,
                    centre_frequency=CHANNEL_WIDTH_HZ
                    * (
                        coarse_channel_start - 0.5 + coarse_channel_bandwidth / 2.0
                    ),  # todo check this
                    integration_time_ms=849,
                    logical_fsp_ids=[],
                    zoom_factor=0,
                )
            ],
        ),
    )

    sbd.csp_configurations.append(csp_configuration)

    pick_targets_and_add_scans(sbd, obs_start, duration, primary_dwell, secondary_dwell, interleave_primary)

    return sbd

def pick_targets_and_add_scans(
    sbd: SBDefinition,
    start_time: Time,
    duration: timedelta,
    primary_dwell: timedelta,
    secondary_dwell: timedelta,
    interleave_primary: bool,
) -> SBDefinition:
    """
    Mutates given SBD, appending targets and scans for any targets that are currently up
    """
    # Serialisation issue in capture_request_response requires args to not be a Time
    # TODO Fix this
    start_time = Time(start_time)
    end_time = Time(start_time + duration)
    while True:
        total_sbd_time = total_scans_time_for_sbd(sbd)
        # Check if after all the scans that are built up so far,
        # there is enough time for at least one more
        current_expected_end_time = start_time + total_sbd_time

        if (current_expected_end_time + primary_dwell) > end_time:
            return sbd

        targets = pick_targets(
            coarse_channel_start=coarse_channel_start_for_sbd(sbd),
            obs_time=current_expected_end_time,
        )

        if targets.primary is None:
            # TODO check with Alec but it makes sense that this results in a shorter SBD rather than
            #  idle telescope time
            msg = f"No more targets available. SBD will run for {total_sbd_time}"
            LOGGER.info(msg)
            return sbd

        primary_target = pdm_target_from_aiv_target(targets.primary)
        sbd.targets.append(primary_target)

        _add_scan_for_target(sbd=sbd, target=primary_target, duration=primary_dwell)
        total_sbd_time += primary_dwell

        for secondary in targets.secondary or []:
            if (total_sbd_time + secondary_dwell) > duration:
                return sbd

            secondary_target = pdm_target_from_aiv_target(secondary)
            sbd.targets.append(secondary_target)
            _add_scan_for_target(sbd=sbd, target=secondary_target, duration=secondary_dwell)
            total_sbd_time += secondary_dwell

            if interleave_primary:
                _add_scan_for_target(sbd=sbd, target=primary_target, duration=primary_dwell)
                total_sbd_time += secondary_dwell


def _add_scan_for_target(sbd: SBDefinition, target: Target, duration: timedelta) -> SBDefinition:
    # Assume one CSP config that we use for every scan
    csp_configuration = sbd.csp_configurations[0]

    scan = ScanDefinition(
        scan_definition_id=scan_definition_id(),
        target_ref=target.target_id,
        csp_configuration_ref=csp_configuration.config_id,
        scan_duration_ms=duration,
    )

    sbd.mccs_allocation.subarray_beams[0].scan_sequence.append(scan)
    return sbd


def pdm_target_from_aiv_target(aiv_target: Row) -> Target:
    return Target(
        target_id=generate_target_id(),
        name=aiv_target["name"],
        reference_coordinate=ICRSCoordinates(
            ra_str=aiv_target["coords"].ra.to_string(u.hour, sep=":"),
            dec_str=aiv_target["coords"].dec.to_string(u.degree, sep=":"),
        ),
    )


def total_scans_time_for_sbd(sbd: SBDefinition) -> timedelta:
    return timedelta(
        seconds=sum(
            scan.scan_duration_ms.seconds
            for scan in sbd.mccs_allocation.subarray_beams[0].scan_sequence
        )
    )


def coarse_channel_start_for_sbd(sbd: SBDefinition):
    if len(sbd.csp_configurations) != 1:
        raise RuntimeError(
            "Error getting the course channel start from the SBD. Expected one CSP Configuration"
        )

    spw = sbd.csp_configurations[0].lowcbf.correlation_spws[0]
    # TODO
    return (spw.centre_frequency / CHANNEL_WIDTH_HZ) - (0.5 * spw.number_of_channels)
