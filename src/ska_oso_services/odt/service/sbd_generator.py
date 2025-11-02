# pylint: disable=no-member
from random import randint
from typing import List, Optional

import astropy.units as u
from ska_oso_pdm import SBDefinition, SubArrayLOW, SubArrayMID, Target, TelescopeType
from ska_oso_pdm._shared import TimedeltaMs
from ska_oso_pdm.project import ObservingBlock, ScienceProgramme
from ska_oso_pdm.sb_definition import (
    CSPConfiguration,
    DishAllocation,
    MCCSAllocation,
    ScanDefinition,
)
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration, MidCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.csp.midcbf import (
    CorrelationSPWConfiguration,
    ReceiverBand,
    Subband,
)
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import (
    Aperture,
    SubarrayBeamConfiguration,
)
from ska_oso_pdm.sb_definition.procedures import GitScript

from ska_oso_services.common.calibrator_strategy import (
    OBSERVATORY_CALIBRATION_STRATEGIES,
    CalibrationWhen,
)
from ska_oso_services.common.calibrators import find_appropriate_calibrator
from ska_oso_services.common.osdmapper import get_osd_data
from ska_oso_services.common.static.constants import (
    LOW_STATION_CHANNEL_WIDTH_MHZ,
    MID_CHANNEL_WIDTH_KHZ,
)


def generate_sbds(obs_block: ObservingBlock) -> list[SBDefinition]:
    """
    This is the main algorithm for generating SBDefinitions for an
    ObservingBlock, using the data defined in the ScienceProgramme

    As a first implementation, it generates a single SBDefinition for each
    ScienceProgramme, with a scan time for each ObservationSet/Target pair
    as defined in the Proposal
    """
    return [
        _sbd_from_science_programme(science_programme)
        for science_programme in obs_block.science_programmes
    ]


def _sbd_from_science_programme(science_programme: ScienceProgramme) -> SBDefinition:
    science_programme.targets = _copy_targets_with_name(science_programme.targets)

    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array

    if telescope == TelescopeType.SKA_LOW:
        # In future we'll get this from the calibration_id but hard coding for now
        calibration_strategy = OBSERVATORY_CALIBRATION_STRATEGIES["highest_elevation"]

    csp_configurations = [_csp_configuration_from_science_programme(science_programme)]

    scan_sequence = []
    targets = []

    for target in science_programme.targets:
        # first adding the science target to the target list and
        # creating the scan_definition for the target

        targets.append(target)
        target_scan_duration_ms = _scan_time_ms_from_science_programme(
            science_programme, target.target_id
        )

        target_csp_configuration_ref = csp_configurations[0].config_id

        # creating the scan sequence for each target, this should
        # allow for easier insertion of the calibrators when we
        # support multiple targets, we can concatenate these list
        # to make the final scan_sequence and target list

        target_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=target_scan_duration_ms,
                target_ref=target.target_id,
                csp_configuration_ref=target_csp_configuration_ref,
            )
        ]

        if telescope == TelescopeType.SKA_LOW:
            # now finding the appropriate calibrators and adding
            # to the target list
            calibrators = find_appropriate_calibrator(
                target, calibration_strategy, target_scan_duration_ms, telescope
            )

            for calibrator in calibrators:
                targets.append(calibrator.calibrator)
                calibrator_scan_definition = ScanDefinition(
                    scan_definition_id=_sbd_internal_id(ScanDefinition),
                    scan_duration_ms=calibration_strategy.duration_ms,
                    target_ref=calibrator.calibrator.target_id,
                    csp_configuration_ref=target_csp_configuration_ref,
                )

                match calibrator.when:
                    case CalibrationWhen.BEFORE_EACH_SCAN:
                        target_scan_sequence.insert(0, calibrator_scan_definition)
                    case CalibrationWhen.AFTER_EACH_SCAN:
                        target_scan_sequence.append(calibrator_scan_definition)

        # adding the target scan sequence to the full scan_sequence
        scan_sequence += target_scan_sequence

    # we've added every calibrator to the target list, but there's
    # a good chance we've got some multiples so getting only the
    # unique targets. Sadly Targets are unhashable so this is
    # my monstrous solution - this can surely be improved

    target_names = [target.name for target in targets]
    indices_of_unique_target = [target_names.index(i) for i in set(target_names)]
    unique_targets = [targets[idx] for idx in indices_of_unique_target]
    # this next bit is to make testing easier
    unique_targets.sort(key=lambda x: x.name)

    mccs_allocation, dish_allocations = _receptor_field_from_science_programme(
        science_programme, scan_sequence
    )

    schedulingblock = SBDefinition(
        telescope=telescope,
        activities=_default_activities(),
        dish_allocations=dish_allocations,
        mccs_allocation=mccs_allocation,
        csp_configurations=csp_configurations,
        targets=unique_targets,
    )

    if telescope == TelescopeType.SKA_LOW:
        # I'm assuming, based on what I can see from the test data that there
        # will be only one calibration_strategy for now
        description = science_programme.calibration_strategies[0].notes
        schedulingblock.description = description

    return schedulingblock


def _default_activities() -> dict[str, GitScript]:
    return {
        "observe": GitScript(
            repo="https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git",
            path="git://scripts/allocate_and_observe_sb.py",
            branch="master",
            commit=None,
        )
    }


def _receptor_field_from_science_programme(
    science_programme: ScienceProgramme, scan_sequence: List[ScanDefinition]
) -> tuple[Optional[MCCSAllocation], Optional[DishAllocation]]:
    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array

    match telescope:
        case TelescopeType.SKA_LOW:
            mccs_allocation = _mccs_allocation(
                SubArrayLOW(observation_set.array_details.subarray.upper()),
                scan_sequence,
            )

            dish_allocations = None
        case TelescopeType.SKA_MID:
            mccs_allocation = None
            dish_allocations = _dish_allocation(
                SubArrayMID(observation_set.array_details.subarray.upper()),
                scan_sequence,
            )
        case _:
            raise ValueError(f"Unsupported TelescopeType {telescope}")

    return mccs_allocation, dish_allocations


def _csp_configuration_from_science_programme(
    science_programme: ScienceProgramme,
) -> CSPConfiguration:
    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array
    match telescope:
        case TelescopeType.SKA_LOW:
            midcbf = None
            observation_type_details = observation_set.observation_type_details
            lowcbf = LowCBFConfiguration(
                do_pst=False,
                correlation_spws=[
                    Correlation(
                        spw_id=1,
                        number_of_channels=int(
                            observation_type_details.bandwidth.to(u.Hz).value
                            / (LOW_STATION_CHANNEL_WIDTH_MHZ * 1e6)
                        ),
                        centre_frequency=observation_type_details.central_frequency.to(
                            u.Hz
                        ).value,
                        integration_time_ms=849,
                        logical_fsp_ids=[],
                        zoom_factor=0,
                    )
                ],
            )
        case TelescopeType.SKA_MID:
            observation_type_details = observation_set.observation_type_details
            midcbf = MidCBFConfiguration(
                frequency_band=_proposal_observing_band_to_mid_receiver_band(
                    observation_set.observing_band
                ),
                subbands=[
                    Subband(
                        correlation_spws=[
                            CorrelationSPWConfiguration(
                                spw_id=1,
                                logical_fsp_ids=[],
                                centre_frequency=(
                                    observation_type_details.central_frequency.to(
                                        u.Hz
                                    ).value
                                ),
                                number_of_channels=int(
                                    observation_type_details.bandwidth.to(u.Hz).value
                                    / (MID_CHANNEL_WIDTH_KHZ * 1e3)
                                ),
                                zoom_factor=0,
                                time_integration_factor=10,
                            )
                        ]
                    )
                ],
            )
            lowcbf = None
        case _:
            raise ValueError(f"Unsupported TelescopeType {telescope}")

    csp_configuration_id, name = _sbd_internal_id_and_name(CSPConfiguration)

    return CSPConfiguration(
        config_id=csp_configuration_id,
        name=name,
        midcbf=midcbf,
        lowcbf=lowcbf,
    )


def _scan_time_ms_from_science_programme(
    science_programme: ScienceProgramme, target_id: str
) -> TimedeltaMs:
    """
    The Proposal contains an integration time per ObservationSet. Either the user has
    input a time then we can just use that for each target, or they input a sensitivity
    and we then need to get the time from the sensitivity calculator results
    """
    if (
        science_programme.observation_sets[
            0
        ].observation_type_details.supplied.supplied_type
        == "integration_time"
    ):
        return TimedeltaMs(
            milliseconds=science_programme.observation_sets[0]
            .observation_type_details.supplied.quantity.to(u.ms)
            .value
        )
    else:
        # The ScienceProgramme contains all the result_details that are
        # linked to the one observation set in the science programme. Therefore,
        # there should only be one result for each target
        result_for_target = next(
            result_detail
            for result_detail in science_programme.result_details
            if result_detail.target_ref == target_id
        )
        return TimedeltaMs(
            milliseconds=result_for_target.result.continuum.to(u.ms).value
        )


def _dish_allocation(
    subarray: SubArrayMID, scan_sequence: List[ScanDefinition]
) -> DishAllocation:
    osd_data = get_osd_data(
        array_assembly=subarray.value, capabilities="mid", source="car"
    )
    dish_ids = osd_data["capabilities"]["mid"][subarray.value]["number_dish_ids"]

    return DishAllocation(
        dish_allocation_id=_sbd_internal_id(DishAllocation),
        selected_subarray_definition=subarray,
        dish_ids=dish_ids,
        scan_sequence=scan_sequence,
    )


def _mccs_allocation(
    subarray: SubArrayLOW, scan_sequence: List[ScanDefinition]
) -> MCCSAllocation:
    osd_data = get_osd_data(
        array_assembly=subarray.value, capabilities="low", source="car"
    )

    station_ids = osd_data["capabilities"]["low"][subarray.value]["number_station_ids"]

    apertures = [
        Aperture(station_id=station_id, weighting_key="uniform", substation_id=1)
        for station_id in station_ids
    ]

    return MCCSAllocation(
        mccs_allocation_id=_sbd_internal_id(MCCSAllocation),
        selected_subarray_definition=subarray,
        subarray_beams=[
            SubarrayBeamConfiguration(
                apertures=apertures, subarray_beam_id=1, scan_sequence=scan_sequence
            )
        ],
    )


def _proposal_observing_band_to_mid_receiver_band(observing_band: str) -> ReceiverBand:
    """
    Maps the value that the PHT sets in the Proposal for the band to the Receiver Band.

    TODO After refactoring the Proposal and the SBDefinition should use the
        same ReceiverBand so this can go away
    """
    match observing_band:
        case "mid_band_1":
            return ReceiverBand.BAND_1
        case "mid_band_2":
            return ReceiverBand.BAND_2
        case "mid_band_3":
            return ReceiverBand.BAND_5A
        case "mid_band_4":
            return ReceiverBand.BAND_5B
        case _:
            raise ValueError(f"Mid Band {observing_band} not supported")


def _sbd_internal_id(pdm_type: type) -> str:
    """
    Creates an identifier for a component of the SBDefinition that can
    be used for tracking relationships
    """
    mapping = {
        MCCSAllocation: "mccs-allocation-{}",
        DishAllocation: "dish-allocation-{}",
        ScanDefinition: "scan-definition-{}",
    }

    return mapping[pdm_type].format(randint(10000, 99999))


def _sbd_internal_id_and_name(pdm_type: type) -> tuple[str, str]:
    """
    Creates an identifier for a component of the SBDefinition thar can
    be used for tracking relationships alongside a display name that a user
    could edit
    """
    random_int = randint(10000, 99999)

    mapping = {
        CSPConfiguration: (f"csp-configuration-{random_int}", f"Config {random_int}")
    }

    return mapping[pdm_type]


def _copy_targets_with_name(targets: list[Target]) -> list[Target]:
    """
    The PHT creates a Proposal with a Target with the target_id populated but not the
    name. Here we populate the name with the ID that is set in the Proposal, assuming
    it is unique. Longer term we should standardise how these fields are set.
    """
    return [
        target.model_copy(update={"name": target.target_id}, deep=True)
        for target in targets
    ]
