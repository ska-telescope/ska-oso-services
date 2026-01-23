# pylint: disable=no-member
from ska_oso_pdm.sb_definition import MCCSAllocation

from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
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
    validators = [validate_number_subarray_beams]
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
