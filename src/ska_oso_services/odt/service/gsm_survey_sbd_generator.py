"""
Generator of SBDefinitions for the Global Sky Model survery commissioning use case.

This will take pointings from an input file, along with other parameters, and generates
(number of pointings / (num_subarray_beams * num_scans)) SBDefinitions
"""

from __future__ import annotations

from datetime import timedelta
from math import floor

# pylint: disable=no-member
from astropy import units as u
from astropy.units import Quantity
from ska_oso_pdm import ICRSCoordinates, SBDefinition, SubArrayLOW, Target, TelescopeType
from ska_oso_pdm.sb_definition import (
    CSPConfiguration,
    MCCSAllocation,
    ScanDefinition,
    SDPConfiguration,
    SDPScript,
)
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import Aperture, SubarrayBeamConfiguration
from ska_oso_pdm.sb_definition.procedures import GitScript

from ska_oso_services.common.astro import low_frequency_to_coarse_channel
from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.odt.service.sbd_generator import _sbd_internal_id

DEFAULT_SUBARRAY = SubArrayLOW.AA2_ALL


def _low_default_subarray_parameters() -> tuple[list[int], Quantity]:
    station_ids = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_LOW, DEFAULT_SUBARRAY, "number_station_ids"
    )
    total_bandwidth = (
        get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_LOW, DEFAULT_SUBARRAY, "available_bandwidth_hz"
        )
        * u.Hz
    )
    return station_ids, total_bandwidth


CALIBRATOR_TARGET = Target(
    target_id="calibrator-00000",
    name="Polaris Australis",
    reference_coordinate=ICRSCoordinates(ra_str="21:08:46.8636", dec_str="-88:57:23.398"),
)


def generate_gsm_survey_sbds(
    input_targets: list[Target],
    centre_frequency: Quantity,
    scan_duration: timedelta,
    num_subarray_beams: int,
    num_scans: int,
    num_calibrator_beams: int,
) -> list[SBDefinition]:

    sbds = []
    station_ids, total_bandwidth = _low_default_subarray_parameters()

    number_of_channels = _get_number_of_channels_for_each_subarray_beam(
        num_subarray_beams + num_calibrator_beams, total_bandwidth
    )

    total_targets = len(input_targets)

    csp_configuration = _csp_configuration(
        centre_frequency=centre_frequency, number_of_channels=number_of_channels
    )

    apertures = [
        Aperture(station_id=station_id, weighting_key="uniform", substation_id=1)
        for station_id in station_ids
    ]

    # This is where you would apply some kind of clustering algorithm
    # that decides how to break the list of targets into SBDs.
    # This basic first implementation just fills each SBD with num_subarray_beams * num_scans
    # targets until it runs out of targets, then creates a final SBD with the remaining targets.
    num_targets_per_sbd = num_scans * num_subarray_beams
    num_full_sbds = total_targets // num_targets_per_sbd

    for index in range(0, num_full_sbds * num_targets_per_sbd, num_targets_per_sbd):

        targets_for_sbd = input_targets[index : index + num_targets_per_sbd]

        sbds.append(
            _sbd_for_calibrator_targets(
                targets_for_sbd,
                csp_configuration,
                scan_duration,
                num_subarray_beams,
                num_scans,
                apertures,
                num_calibrator_beams,
            )
        )

    # Handle remaining targets that don't fill a complete SBD with the requested
    # number of subarray beams. This may result in an SBD with fewer subarray
    # beams than requested but will guarantee each subarray beam has the same number of scans
    remainder = total_targets - (num_full_sbds * num_targets_per_sbd)
    if remainder > 0:
        remainder_targets = input_targets[num_full_sbds * num_targets_per_sbd :]
        remainder_beams, remainder_scans = _compute_remainder_layout(remainder, num_subarray_beams)
        sbds.append(
            _sbd_for_calibrator_targets(
                remainder_targets,
                csp_configuration,
                scan_duration,
                remainder_beams,
                remainder_scans,
                apertures,
                num_calibrator_beams,
            )
        )

    return sbds


def _compute_remainder_layout(num_remaining: int, max_beams: int) -> tuple[int, int]:
    """
    Find the best (num_beams, scans_per_beam) layout for leftover targets.

    Each subarray beam in an SBD must have the same number of scans, so
    we need num_remaining = num_beams * scans_per_beam.  We pick the
    largest num_beams <= max_beams that divides the num_remainingevenly.
    """
    for beams in range(min(max_beams, num_remaining), 0, -1):
        if num_remaining % beams == 0:
            return beams, num_remaining // beams
    return 1, num_remaining


def _get_number_of_channels_for_each_subarray_beam(
    num_subarray_beams: int, total_bandwidth: Quantity
) -> int:
    """
    The number_of_channels in the CSPConfiguration for each scan must be a multiple
    of 8 coarse channels.

    Given the SBD generation wants to make use of the full bandwidth available, splitting this
    across any num_subarray_beams given in the input may result in an invalid number_of_channels.

    This function will return the closest valid number_of_channels for the num_subarray_beams.
    """

    exact_coarse_channel = low_frequency_to_coarse_channel(total_bandwidth / num_subarray_beams)

    return floor(exact_coarse_channel / 8) * 8


def _csp_configuration(centre_frequency: Quantity, number_of_channels: int) -> CSPConfiguration:
    return CSPConfiguration(
        config_id="csp-configuration-12345",
        name=f"CSP {centre_frequency}, {number_of_channels} channels",
        lowcbf=LowCBFConfiguration(
            do_pst=False,
            correlation_spws=[
                Correlation(
                    spw_id=1,
                    number_of_channels=number_of_channels,
                    centre_frequency=centre_frequency.to(u.Hz).value,
                    integration_time_ms=timedelta(seconds=849e-3),
                    logical_fsp_ids=[],
                    zoom_factor=0,
                )
            ],
        ),
    )


def _sbd_for_calibrator_targets(
    targets: list[Target],
    csp_configuration: CSPConfiguration,
    scan_duration: timedelta,
    num_subarray_beams: int,
    num_scans: int,
    apertures: list[Aperture],
    num_calibrator_beams: int,
) -> SBDefinition:
    """
    Creates a single SBD for the input targets, creating a number of scans
    for each subarray beam (i.e. this assumes len(targets) == num_subarray_beams * num_scans)
    """
    if len(targets) != num_subarray_beams * num_scans:
        raise ValueError(
            f"Expected {num_subarray_beams * num_scans} targets "
            f"({num_subarray_beams} beams x {num_scans} scans), "
            f"but got {len(targets)}"
        )

    subarray_beams = []

    for subarray_beam_index in range(0, num_subarray_beams):

        targets_for_subarray_beam = targets[
            subarray_beam_index * num_scans : (subarray_beam_index + 1) * num_scans
        ]

        subarray_beam_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=scan_duration,
                target_ref=target.target_id,
                csp_configuration_ref=csp_configuration.config_id,
                scan_intent="Science",
            )
            for target in targets_for_subarray_beam
        ]

        subarray_beams.append(
            SubarrayBeamConfiguration(
                apertures=apertures,
                subarray_beam_id=subarray_beam_index + 1,
                scan_sequence=subarray_beam_scan_sequence,
            )
        )

    for _ in range(0, num_calibrator_beams):
        subarray_beam_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=scan_duration,
                target_ref=CALIBRATOR_TARGET.target_id,
                csp_configuration_ref=csp_configuration.config_id,
                scan_intent="Calibrator",
            )
            for _ in range(0, num_scans)
        ]

        subarray_beams.append(
            SubarrayBeamConfiguration(
                apertures=apertures,
                subarray_beam_id=len(subarray_beams) + 1,
                scan_sequence=subarray_beam_scan_sequence,
            )
        )

    mccs_allocation = MCCSAllocation(
        mccs_allocation_id=_sbd_internal_id(MCCSAllocation),
        selected_subarray_definition=DEFAULT_SUBARRAY,
        subarray_beams=subarray_beams,
    )

    sdp_configurations = [
        SDPConfiguration(
            sdp_script=SDPScript.VIS_RECEIVE,
            script_version="latest",
            script_parameters={},
        )
    ]

    if num_calibrator_beams is not None and num_calibrator_beams > 0:
        targets += [CALIBRATOR_TARGET]

    return SBDefinition(
        telescope=TelescopeType.SKA_LOW,
        activities=_default_activities(),
        mccs_allocation=mccs_allocation,
        csp_configurations=[csp_configuration],
        sdp_configurations=sdp_configurations,
        targets=targets,
    )


def _default_activities() -> dict[str, GitScript]:
    return {
        "observe": GitScript(
            repo="https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git",
            path="git://scripts/allocate_and_observe_sb.py",
            branch="master",
            commit=None,
        )
    }
