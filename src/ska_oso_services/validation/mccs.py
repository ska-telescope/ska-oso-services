# pylint: disable=no-member
import dataclasses

import astropy.units as u
from ska_oso_pdm import ValidationArrayAssembly
from ska_oso_pdm.sb_definition import MCCSAllocation, ScanDefinition
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import SubarrayBeamConfiguration

from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.validation.csp import calculate_continuum_spw_bandwidth
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    check_relevant_context_contains,
    validate,
    validator,
)


@validator
def validate_mccs(mccs_context: ValidationContext[MCCSAllocation]) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing a MCCS Allocation
        to be validated
    :return: the collated ValidationIssues resulting from applying each of
            the relevant MCCS Validators to the MCCS Allocation
    """
    validators = [
        validate_number_subarray_beams,
        validate_number_substations,
        validate_number_of_pst_beams_per_scan,
        validate_subarray_beams_per_scan_have_the_same_duration,
        validate_station_bandwidth,
    ]
    return validate(mccs_context, validators)


@validator
def validate_number_subarray_beams(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing an MCCS Allocation to
        be validated
    :return: a validation error if the number of subarray beams in the allocation
        exceeds the number permitted for the array assembly being validated against
    """
    number_subarray_beams = len(mccs_context.primary_entity.subarray_beams)

    allowed_subarray_beams = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_subarray_beams"
    )
    if number_subarray_beams > allowed_subarray_beams:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"number of subarray beams {number_subarray_beams} "
                f"exceeds allowed {allowed_subarray_beams} for {mccs_context.array_assembly}",
            )
        ]

    return []


@validator
def validate_number_substations(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing an MCCS Allocation to
        be validated
    :return: a validation error if the number of substations in a subarray beam
        in the allocation exceeds the number permitted for the array assembly being
         validated against
    """
    mccs_allocation = mccs_context.primary_entity

    allowed_number_of_substations = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_substations"
    )

    validation_issues = []
    for subarray_beam in mccs_allocation.subarray_beams:
        # special rule of AA0.5, because it's a bit more complicated

        if mccs_context.array_assembly == ValidationArrayAssembly.AA05:
            number_of_stations = len(
                [station for station in subarray_beam.apertures if station.substation_id == 1]
            )
            total_number_of_substations = len(subarray_beam.apertures) - number_of_stations

        else:
            total_number_of_substations = len(subarray_beam.apertures)

        if total_number_of_substations > allowed_number_of_substations:
            validation_issues.append(
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    field=f"$mccs_allocation.subarray_beams[{subarray_beam.subarray_beam_id - 1}]",
                    message=f"max number of substations {total_number_of_substations} "
                    f"in subarray beam {subarray_beam.subarray_beam_id} exceeds allowed"
                    f" {allowed_number_of_substations} for {mccs_context.array_assembly}",
                )
            )

    return validation_issues


# These don't feel like an MCCS validator - but the structure of the SBD, the fact
# that beams have scans, rather than scans having beams, means we need to pull this
# up a level to access what we need.
@validator
def validate_number_of_pst_beams_per_scan(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing an MCCS Allocation to
        be validated
    :return: a validation error if the number of PST tied array beams in a scan,
        across all subarray beams, does not exceed the number permitted for the
        array assembly being validated against
    """
    check_relevant_context_contains(["targets"], mccs_context)

    allowed_number_pst_beams = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_pst_beams"
    )

    mccs_allocation = mccs_context.primary_entity
    targets = mccs_context.relevant_context["targets"]
    scans = __build_scan_slices(mccs_allocation)

    validation_issues = []
    for scan in scans:
        target_refs = [beam_scan.scan.target_ref for beam_scan in scan.beam_scans]
        number_pst_beams = 0

        for ref in target_refs:
            number_pst_beams += sum(
                len(target.tied_array_beams.pst_beams)
                for target in targets
                if target.target_id == ref
            )

        if number_pst_beams > allowed_number_pst_beams:
            validation_issues.append(
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    message=f"number of PST beams {number_pst_beams} for scan {scan.index + 1} "
                    f"exceeds allowed {allowed_number_pst_beams} for "
                    f"{mccs_context.array_assembly}",
                )
            )

    return validation_issues


@validator
def validate_subarray_beams_per_scan_have_the_same_duration(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing an MCCS Allocation to
        be validated
    :return: a validation error if the subarray beams in a scan do not
        have the same scan duration
    """
    mccs_allocation = mccs_context.primary_entity

    scans = __build_scan_slices(mccs_allocation)

    validation_issues = []
    for scan in scans:
        scan_durations = len(
            {beam_scan.scan.scan_duration.to(u.s) for beam_scan in scan.beam_scans}
        )

        if scan_durations > 1:
            validation_issues.append(
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    message=f"The scan durations for scan {scan.index + 1} "
                    "are not equal for all subarray beams",
                )
            )

    return validation_issues


@validator
def validate_station_bandwidth(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    :param mccs_context: a ValidationContext containing an MCCS Allocation to
        be validated
    :return: a validation error if the total bandwidth in a scan, summed over
        all subarray beams, spectral windows and substations/apertures does
        not exceed the allowed value for the array assembly being validated
        against
    """

    check_relevant_context_contains(["csp_config"], mccs_context)
    csp_configs = mccs_context.relevant_context["csp_config"]

    mccs_allocation = mccs_context.primary_entity

    available_bandwidth = (
        get_subarray_specific_parameter_from_osd(
            mccs_context.telescope, mccs_context.array_assembly, "available_bandwidth_hz"
        )
        * u.Hz
    )

    validation_issues = []

    # this is the SBD in "scan space" i.e. where scans are split into subarray beams
    scans = __build_scan_slices(mccs_allocation)

    # for each scan in the SBD, there are subarray beam scans
    for scan in scans:
        # then getting the csp details and substation info for each subarray beam scan
        beam_bandwidths = []
        beam_max_stations = []
        for beam in scan.beam_scans:
            max_number_of_substations = max(
                [station.substation_id for station in beam.beam.apertures]
            )
            csp_config = next(
                csp_config
                for csp_config in csp_configs
                if csp_config.config_id == beam.scan.csp_configuration_ref
            )

            # now calculating the bandwidth for each spectral window in a
            # subarray beam
            spw_bandwidths = [
                calculate_continuum_spw_bandwidth(
                    ValidationContext(
                        primary_entity=spw,
                        source_jsonpath=f"$.subarray_beams[{beam.beam.subarray_beam_id - 1}]",
                        telescope=mccs_context.telescope,
                        array_assembly=mccs_context.array_assembly,
                    )
                )
                for spw in csp_config.lowcbf.correlation_spws
            ]

            # appending the summed bandwidth to the beam bandwidths list
            beam_bandwidths.append(sum(spw_bandwidths))
            beam_max_stations.append(max_number_of_substations)

        max_total_bandwith = sum(beam_bandwidths) * max(beam_max_stations)

        if max_total_bandwith > available_bandwidth:
            validation_issues.append(
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    field="$.subarray_beams",
                    message=f"At least one station is using more bandwidth "
                    f"({max_total_bandwith.to(u.MHz).value} MHz) than is "
                    f"available ({available_bandwidth.to(u.MHz).value} MHz)"
                    f"for array assembly {mccs_context.array_assembly}",
                )
            )

        return validation_issues


@dataclasses.dataclass(frozen=True)
class BeamScan:
    beam: SubarrayBeamConfiguration
    scan: ScanDefinition


@dataclasses.dataclass
class ScanSlice:
    index: int
    beam_scans: list[BeamScan]


def __build_scan_slices(mccs_allocation: MCCSAllocation) -> list[ScanSlice]:
    """
    private function to invert the SBD logic and express the observation as "scans that have beams"
    rather than "beams that have scans"
    """

    beams = mccs_allocation.subarray_beams

    scan_count = {len(subarray_beam.scan_sequence) for subarray_beam in beams}

    # we enforce this in the ODT but adding for defensiveness
    if len(scan_count) != 1:
        raise ValueError("All subarray beams should have the same number of scans")

    slices = []
    for idx, scans in enumerate(zip(*(subarray_beam.scan_sequence for subarray_beam in beams))):
        beam_scans = [BeamScan(beam=beam, scan=scan) for beam, scan in zip(beams, scans)]
        slices.append(ScanSlice(index=idx, beam_scans=beam_scans))

    return slices
