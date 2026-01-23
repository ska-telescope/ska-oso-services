# pylint: disable=no-member
from __future__ import annotations

import logging
from functools import singledispatch
from random import randint
from typing import Any, Optional

import astropy.units as u
from ska_oso_pdm import SBDefinition, SubArrayLOW, SubArrayMID, Target, TelescopeType
from ska_oso_pdm._shared import TimedeltaMs
from ska_oso_pdm.project import ObservingBlock, ScienceProgramme
from ska_oso_pdm.proposal.data_product_sdp import (
    DataProductSDP,
    Polarisation,
    ProductType,
    ProductVariant,
    Weighting,
)
from ska_oso_pdm.sb_definition import (
    CSPConfiguration,
    DishAllocation,
    MCCSAllocation,
    ScanDefinition,
    SDPConfiguration,
    SDPScript,
)
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration, MidCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.csp.midcbf import CorrelationSPWConfiguration, ReceiverBand, Subband
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import Aperture, SubarrayBeamConfiguration
from ska_oso_pdm.sb_definition.procedures import GitScript

from ska_oso_services.common.calibrator_strategy import (
    CalibrationWhen,
    lookup_observatory_calibration_strategy,
)
from ska_oso_services.common.calibrators import find_appropriate_calibrators
from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.common.sdpmapper import get_script_versions
from ska_oso_services.common.static.constants import low_station_channel_width, mid_channel_width

LOGGER = logging.getLogger(__name__)
DEFAULT_CALIBRATION_STRATEGY = "highest_elevation"


def generate_sbds(obs_block: ObservingBlock) -> list[SBDefinition]:
    """
    This is the main algorithm for generating SBDefinitions for an
    ObservingBlock, using the data defined in the ScienceProgramme

    As a first implementation, it generates a single SBDefinition for each
    ScienceProgramme, with a scan time for each ObservationSet/Target pair
    as defined in the Proposal
    """
    return [
        _sbd_from_science_programme(science_programme, obs_block.obs_block_id)
        for science_programme in obs_block.science_programmes
    ]


def _sbd_from_science_programme(science_programme: ScienceProgramme, ob_ref: str) -> SBDefinition:
    science_programme.targets = _copy_targets_with_name(science_programme.targets)

    observation_set = science_programme.observation_sets[0]

    telescope = observation_set.array_details.array

    csp_configurations = [_csp_configuration_from_science_programme(science_programme)]

    scan_sequence = []
    # Keep track of the calibrators so we don't end up duplicating them in the SBD
    calibrators_in_use: dict[str, Target] = {}

    # Loop over the targets, creating a scan for each plus any required calibrators
    for target in science_programme.targets:
        target_scan_duration_ms = _scan_time_ms_from_science_programme(
            science_programme, target.target_id
        )

        # Currently there is only one CSP config to be used by all scans
        target_csp_configuration_ref = csp_configurations[0].config_id
        # Define the scan sequence for this target, which can then be
        # updated with calibrators
        target_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=target_scan_duration_ms,
                target_ref=target.target_id,
                csp_configuration_ref=target_csp_configuration_ref,
                scan_intent="Science",
            )
        ]

        # Calibration only currently applies for Low SBD generation
        if telescope == TelescopeType.SKA_LOW:
            # Eventually we expect the strategy to come from the science programme
            # (that has been copied from the proposal) but for now we just hard
            # code the default
            calibration_strategy = lookup_observatory_calibration_strategy(
                DEFAULT_CALIBRATION_STRATEGY
            )

            calibrators = find_appropriate_calibrators(
                target, calibration_strategy, target_scan_duration_ms, telescope
            )

            for calibrator in calibrators:
                calibrators_in_use[calibrator.calibrator.target_id] = calibrator.calibrator

                calibrator_scan_definition = ScanDefinition(
                    scan_definition_id=_sbd_internal_id(ScanDefinition),
                    scan_duration_ms=calibration_strategy.duration_ms,
                    target_ref=calibrator.calibrator.target_id,
                    csp_configuration_ref=target_csp_configuration_ref,
                    scan_intent="Calibrator",
                )

                match calibrator.when:
                    case CalibrationWhen.BEFORE_EACH_SCAN:
                        target_scan_sequence.insert(0, calibrator_scan_definition)
                    case CalibrationWhen.AFTER_EACH_SCAN:
                        target_scan_sequence.append(calibrator_scan_definition)

        # adding the target scan sequence to the full scan_sequence
        scan_sequence += target_scan_sequence

    targets = science_programme.targets + list(calibrators_in_use.values())

    mccs_allocation, dish_allocations = _receptor_field_from_science_programme(
        science_programme, scan_sequence
    )

    sdp_configurations = [
        SDPConfiguration(
            sdp_script=SDPScript.VIS_RECEIVE,
            script_version="latest",
            script_parameters={},
        )
    ]
    if science_programme.data_product_sdps:
        sdp_configurations.extend(
            [
                _sdp_configuration_from_data_product_sdp(dp_sdp)
                for dp_sdp in science_programme.data_product_sdps
                if dp_sdp is not None
            ]
        )

    sbd = SBDefinition(
        ob_ref=ob_ref,
        telescope=telescope,
        activities=_default_activities(),
        dish_allocations=dish_allocations,
        mccs_allocation=mccs_allocation,
        csp_configurations=csp_configurations,
        sdp_configurations=sdp_configurations,
        targets=targets,
    )

    if (
        science_programme.calibration_strategies
        and science_programme.calibration_strategies[0].notes
    ):
        sbd.description = science_programme.calibration_strategies[0].notes

    return sbd


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
    science_programme: ScienceProgramme, scan_sequence: list[ScanDefinition]
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
                            observation_type_details.bandwidth / low_station_channel_width()
                        ),
                        centre_frequency=observation_type_details.central_frequency.to(u.Hz).value,
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
                                    observation_type_details.central_frequency.to(u.Hz).value
                                ),
                                number_of_channels=int(
                                    observation_type_details.bandwidth / mid_channel_width()
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


def _sdp_configuration_from_data_product_sdp(
    dp_sdp: DataProductSDP,
) -> SDPConfiguration | None:
    @singledispatch
    def convert_parameter(value: Any) -> Any:
        return value

    @convert_parameter.register
    def _(value: list) -> str | list:
        if all(isinstance(v, Polarisation) for v in value):
            return "".join(value)
        return value

    @convert_parameter.register
    def _(value: u.quantity.Quantity) -> float:
        return value.value

    @convert_parameter.register
    def _(value: Weighting) -> str:
        return f"{value.weighting} {value.robust}" if value.robust is not None else value.weighting

    if (
        dp_sdp.script_parameters.kind is not ProductType.CONTINUUM
        and dp_sdp.script_parameters.variant is not ProductVariant.CONTINUUM_IMAGE
    ):
        LOGGER.warning(
            "Script parameters of %s kind with variant %s are not supported "
            "by Scheduling Blocks. Currently the only supported kind is %s with %s. "
            "The unsupported parameters will be ignored in SBD conversion.",
            dp_sdp.script_parameters.kind,
            dp_sdp.script_parameters.variant,
            ProductType.CONTINUUM,
            ProductVariant.CONTINUUM_IMAGE,
        )
        return None

    parameters_to_ignore = ["kind", "variant", "gaussian_taper"]

    astropy_unit_mapper = {  # Units expected by the continuum-imaging SDP script
        "image_size": "pix",
        "image_cellsize": "arcsec",
    }
    parameters = {}
    for param_key, param_value in vars(dp_sdp.script_parameters).items():
        if param_key not in parameters_to_ignore:
            if isinstance(param_value, u.quantity.Quantity):
                param_value = param_value.to(astropy_unit_mapper[param_key])
            parameters[param_key] = convert_parameter(param_value)
    latest_continuum_script_version = (
        get_script_versions(SDPScript.CONTINUUM_IMAGING.value) or ["latest"]
    )[
        -1
    ]  # Use 'latest' if version not found in TMData
    return SDPConfiguration(
        sdp_script=SDPScript.CONTINUUM_IMAGING,
        script_version=latest_continuum_script_version,
        script_parameters={"continuum_imaging": parameters},
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
        science_programme.observation_sets[0].observation_type_details.supplied.supplied_type
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
        return TimedeltaMs(milliseconds=result_for_target.result.continuum.to(u.ms).value)


def _dish_allocation(subarray: SubArrayMID, scan_sequence: list[ScanDefinition]) -> DishAllocation:
    dish_ids = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_MID, subarray, "receptors"
    )

    return DishAllocation(
        dish_allocation_id=_sbd_internal_id(DishAllocation),
        selected_subarray_definition=subarray,
        dish_ids=dish_ids,
        scan_sequence=scan_sequence,
    )


def _mccs_allocation(subarray: SubArrayLOW, scan_sequence: list[ScanDefinition]) -> MCCSAllocation:
    station_ids = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_LOW, subarray, "receptors"
    )

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

    mapping = {CSPConfiguration: (f"csp-configuration-{random_int}", f"Config {random_int}")}

    return mapping[pdm_type]


def _copy_targets_with_name(targets: list[Target]) -> list[Target]:
    """
    The PHT creates a Proposal with a Target with the target_id populated but not the
    name. Here we populate the name with the ID that is set in the Proposal, assuming
    it is unique. Longer term we should standardise how these fields are set.
    """
    return [target.model_copy(update={"name": target.target_id}, deep=True) for target in targets]
