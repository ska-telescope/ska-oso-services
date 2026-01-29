# pylint: disable=no-member
import dataclasses

import astropy.units as u
from ska_oso_pdm import ValidationArrayAssembly
from ska_oso_pdm.sb_definition import MCCSAllocation, ScanDefinition

from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
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
    :param mccs_context: a ValidationContext containing a Target to be validated
    :return: the collated ValidationIssues resulting from applying each of
            the relevant Target Validators to the Target
    """
    validators = [validate_number_subarray_beams, validate_number_substations]
    return validate(mccs_context, validators)


@validator
def validate_number_subarray_beams(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:

    number_subarray_beams = len(mccs_context.primary_entity.subarray_beams)

    allowed_subarray_beams = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_subarray_beams"
    )
    if number_subarray_beams < allowed_subarray_beams:
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
    function to validate that the number of substations in a MCCS subarray beam does not exceed the
    allowed value for a given array assembly

    :param mccs_context: a ValidationContext containing a Target to be validated
    """
    mccs_allocation = mccs_context.primary_entity

    allowed_number_of_substations = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_substations"
    )

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
            return [
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    field=f"$mccs_allocation.subarray_beams[{subarray_beam.subarray_beam_id - 1}]",
                    message=f"total number of substations {total_number_of_substations} "
                    f"in subarray beam {subarray_beam.subarray_beam_id} exceeds allowed"
                    f" {allowed_number_of_substations} for {mccs_context.array_assembly}",
                )
            ]

    return []


# These don't feel like an MCCS validator - but the structure of the SBD, the fact
# that beams have scans, rather than scans having beams, means we need to pull this
# up a level to access what we need.
@validator
def validate_number_of_pst_beams_per_scan(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:

    check_relevant_context_contains(["targets"], mccs_context)

    allowed_number_pst_beams = get_subarray_specific_parameter_from_osd(
        mccs_context.telescope, mccs_context.array_assembly, "number_pst_beams"
    )

    mccs_allocation = mccs_context.primary_entity
    targets = mccs_allocation.relevant_context["targets"]
    scan_slices = __build_scan_slices(mccs_allocation)

    for scans in scan_slices:
        target_refs = [scan.target_ref for scan in scans.scans]
        number_pst_beams = 0

        for ref in target_refs:
            number_pst_beams += sum(
                len(target.tied_array_beams.pst_beams)
                for target in targets
                if target.target_id == ref
            )

        if number_pst_beams > allowed_number_pst_beams:
            return [
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    message=f"number of pst beams {number_pst_beams} for scan {scans.index} "
                    f"exceeds allowed {allowed_number_pst_beams} for "
                    f"{mccs_context.array_assembly}",
                )
            ]

    return []


@validator
def validate_subarray_beams_per_scan_have_the_same_duration(
    mccs_context: ValidationContext[MCCSAllocation],
) -> list[ValidationIssue]:
    """
    function to validate the number of PST beams per scan

    """
    mccs_allocation = mccs_context.primary_entity

    scan_slices = __build_scan_slices(mccs_allocation)

    for scans in scan_slices:
        scan_durations = len({scan.scan_duration.to(u.s) for scan in scans.scans})

        return (
            [
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    message=f"The scan durations for scan {scans.index} are not equal",
                )
            ]
            if scan_durations > 1
            else []
        )


@dataclasses.dataclass
class ScanSlice:
    index: int
    scans: list[ScanDefinition]


def __build_scan_slices(mccs_allocation: MCCSAllocation) -> list[ScanSlice]:
    """
    private function to invert the SBD logic and express the observation as "scans that have beams"
    rather than "beams that have scans"
    """

    scan_count = {
        len(subarray_beam.scan_sequence) for subarray_beam in mccs_allocation.subarray_beams
    }

    # we enforce this in the ODT but adding for defensiveness
    if len(scan_count) != 1:
        raise ValueError("All subarray beams should have the same number of scans")

    slices = []
    for idx, scans in enumerate(
        zip(*(subarray_beam.scan_sequence for subarray_beam in mccs_allocation.subarray_beams))
    ):
        slices.append(ScanSlice(index=idx, scans=list(scans)))

    return slices
