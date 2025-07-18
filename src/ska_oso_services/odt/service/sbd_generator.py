# pylint: disable=no-member
from typing import Optional

import astropy.units as u
from ska_oso_pdm import SBDefinition, SubArrayLOW, SubArrayMID, TelescopeType
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
from ska_ost_osd.rest.api.resources import get_osd

from ska_oso_services.common.constants import (
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

    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array

    mccs_allocation, dish_allocations = _receptor_field_from_science_programme(
        science_programme
    )

    csp_configurations = [_csp_configuration_from_science_programme(science_programme)]

    scan_definitions = []
    scan_sequence = []
    for index, target in enumerate(science_programme.targets):
        scan_definition = ScanDefinition(
            scan_definition_id=f"scan-definition-{(index + 1):05}",
            scan_duration_ms=_scan_time_ms_from_science_programme(
                science_programme, target.target_id
            ),
            target_ref=target.target_id,
            mccs_allocation_ref=(
                mccs_allocation.mccs_allocation_id
                if mccs_allocation is not None
                else None
            ),
            dish_allocation_ref=(
                dish_allocations.dish_allocation_id
                if dish_allocations is not None
                else None
            ),
            csp_configuration_ref=csp_configurations[0].config_id,
        )

        scan_definitions.append(scan_definition)
        scan_sequence.append(scan_definition.scan_definition_id)

    return SBDefinition(
        telescope=telescope,
        activities=_default_activities(),
        dish_allocations=dish_allocations,
        mccs_allocation=mccs_allocation,
        csp_configurations=csp_configurations,
        targets=science_programme.targets,
        scan_definitions=scan_definitions,
        scan_sequence=scan_sequence,
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


def _receptor_field_from_science_programme(
    science_programme: ScienceProgramme,
) -> tuple[Optional[MCCSAllocation], Optional[DishAllocation]]:
    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array

    match telescope:
        case TelescopeType.SKA_LOW:
            mccs_allocation = _mccs_allocation(
                SubArrayLOW(observation_set.array_details.subarray.upper())
            )

            dish_allocations = None
        case TelescopeType.SKA_MID:
            mccs_allocation = None
            dish_allocations = _dish_allocation(
                SubArrayMID(observation_set.array_details.subarray.upper())
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
                            / (LOW_STATION_CHANNEL_WIDTH_MHZ * 10e6)
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
                                    / (MID_CHANNEL_WIDTH_KHZ * 10e3)
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

    return CSPConfiguration(
        config_id="csp-configuration-00001", midcbf=midcbf, lowcbf=lowcbf
    )


def _scan_time_ms_from_science_programme(
    science_programme: ScienceProgramme, target_id: str
) -> float:
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
        return (
            science_programme.observation_sets[0]
            .observation_type_details.supplied.quantity.to(u.s)
            .value
            * 1e3
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
        return result_for_target.result.continuum.to(u.s).value * 1e3


def _dish_allocation(subarray: SubArrayMID) -> DishAllocation:
    osd_data = get_osd(array_assembly=subarray.value, capabilities="mid", source="car")

    dish_ids = osd_data["capabilities"]["mid"][subarray.value]["number_dish_ids"]

    return DishAllocation(
        dish_allocation_id="dish-allocation-00001",
        selected_subarray_definition=subarray,
        dish_ids=dish_ids,
    )


def _mccs_allocation(subarray: SubArrayLOW) -> MCCSAllocation:
    osd_data = get_osd(array_assembly=subarray.value, capabilities="low", source="car")

    station_ids = osd_data["capabilities"]["low"][subarray.value]["number_station_ids"]

    apertures = [
        Aperture(station_id=station_id, weighting_key="uniform", substation_id=1)
        for station_id in station_ids
    ]

    return MCCSAllocation(
        mccs_allocation_id="mccs-allocation-00001",
        selected_subarray_definition=subarray,
        subarray_beams=[
            SubarrayBeamConfiguration(apertures=apertures, subarray_beam_id=1)
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
