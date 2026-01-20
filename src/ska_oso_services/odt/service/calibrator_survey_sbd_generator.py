"""
This is a very crude strawman script to generate a set of SBDefinitions given an input set of targets.

The SBDefinition for Low has NUM_SUBARRAY_BEAMS subarray beams, each with a scan sequence containing SCANS_PER_SBD scans.
Therefore, each SBDefinition contains NUM_SUBARRAY_BEAMS * SCANS_PER_SBD possible target scans, and this script
will generate len(INPUT_TARGETS) / (NUM_SUBARRAY_BEAMS * SCANS_PER_SBD) SBDefinitions.

Note NUM_SUBARRAY_BEAMS is a constant here. This could be more dynamic, e.g. create a mix of SBDefinitions with different 
numbers of subarray beams that the scheduler could then decide when to execute.

Each scan has a duration of SCAN_DURATION_S so the total time for the SBDefinition is SCAN_DURATION_S * SCANS_PER_SBD.

As a first pass this script uses the same CSP setup for every scan - will some details of CSP setup for each target be
provided in the input as some kind of tuple?

This script also does not add any calibrator scans in. Are calibrator scans part of every SBD? Only some SBDs? Or are there
specific calibrator SBDs that do not contain any of the input targets?

The difficult part is deciding which targets should go in which SBD (i.e. the clustering). This also depends on
the inputs to the script - are the input targets just a list, or already in some kind of structured data?
"""

from __future__ import annotations

from ska_oso_pdm import (
    ICRSCoordinates,
    SBDefinition,
    SubArrayLOW,
    Target,
    TelescopeType,
)
from ska_oso_pdm.builders.target_builder import LowTargetBuilder
from ska_oso_pdm.sb_definition import (
    CSPConfiguration,
    MCCSAllocation,
    ScanDefinition,
    SDPConfiguration,
    SDPScript,
)
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import (
    Aperture,
    SubarrayBeamConfiguration,
)
from ska_oso_pdm.sb_definition.procedures import GitScript

from ska_oso_services.common.osdmapper import get_osd_data
from ska_oso_services.common.static.constants import LOW_STATION_CHANNEL_WIDTH_MHZ
from ska_oso_services.odt.service.sbd_generator import _sbd_internal_id

SCAN_DURATION_S = 600
NUM_SUBARRAY_BEAMS = 2
SCANS_PER_SBD = 1

INPUT_TARGETS: list[Target] = [
    LowTargetBuilder(
        name="47 Tuc",
        reference_coordinate=ICRSCoordinates(
            ra_str="00:24:05.3590", dec_str="-72:04:53.200"
        ),
    ),
    LowTargetBuilder(
        name="SMC",
        reference_coordinate=ICRSCoordinates(
            ra_str="00:52:44.800", dec_str="-72:49:43.00"
        ),
    ),
    LowTargetBuilder(
        name="NGC 362",
        reference_coordinate=ICRSCoordinates(
            ra_str="01:03:14.260", dec_str="-70:50:55.60"
        ),
    ),
    LowTargetBuilder(
        name="LMC",
        reference_coordinate=ICRSCoordinates(
            ra_str="05:23:34.600", dec_str="-69:45:22.00"
        ),
    ),
]

DEFAULT_CSP_CONFIGURATION = CSPConfiguration(
    config_id="csp-configuration-123",
    name="Config 123",
    lowcbf=LowCBFConfiguration(
        do_pst=False,
        correlation_spws=[
            Correlation(
                spw_id=1,
                number_of_channels=int(75 / (LOW_STATION_CHANNEL_WIDTH_MHZ * 1e6)),
                centre_frequency=199.609375 * 1e6,
                integration_time_ms=849,
                logical_fsp_ids=[],
                zoom_factor=0,
            )
        ],
    ),
)

DEFAULT_SUBARRAY = SubArrayLOW.AA2_ALL


def generate_sbds(input_targets: list[Target]) -> list[SBDefinition]:

    sbds = []

    total_targets = len(input_targets)

    # This is where you would apply some kind of clustering algorithm
    # that decides how to break the list of targets into SBDs.
    # This crudely just loops over the input and adds as many targets
    # as there are subarray beams
    for index in range(0, total_targets, NUM_SUBARRAY_BEAMS):

        targets_for_sbd = input_targets[index : index + NUM_SUBARRAY_BEAMS]

        sbds.append(_sbd_for_calibrator_targets(targets_for_sbd))

    return sbds


def _sbd_for_calibrator_targets(targets: list[Target]) -> SBDefinition:
    """
    Creates a single SBD for the input targets, creating a single scan
    for each subarray beam (i.e. this assumes len(targets) == NUM_SUBARRAY_BEAMS)
    """
    assert len(targets) == NUM_SUBARRAY_BEAMS

    csp_configurations = [DEFAULT_CSP_CONFIGURATION]

    osd_data = get_osd_data(
        array_assembly=DEFAULT_SUBARRAY.value, capabilities="low", source="car"
    )
    station_ids = osd_data["capabilities"]["low"][DEFAULT_SUBARRAY.value][
        "number_station_ids"
    ]
    apertures = [
        Aperture(station_id=station_id, weighting_key="uniform", substation_id=1)
        for station_id in station_ids
    ]

    subarray_beams = []

    for target in targets:

        scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=SCAN_DURATION_S,
                target_ref=target.target_id,
                csp_configuration_ref=csp_configurations[0].config_id,
                scan_intent="Science",
            )
        ]

        # TODO here you could append calibrator scans before or after your science scan

        subarray_beams.append(
            SubarrayBeamConfiguration(
                apertures=apertures, subarray_beam_id=1, scan_sequence=scan_sequence
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

    return SBDefinition(
        telescope=TelescopeType.SKA_LOW,
        activities=_default_activities(),
        mccs_allocation=mccs_allocation,
        csp_configurations=csp_configurations,
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


print(generate_sbds(INPUT_TARGETS))
