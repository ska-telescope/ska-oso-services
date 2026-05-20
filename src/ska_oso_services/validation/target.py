# pylint: disable=no-member
import astropy.units as u
from astropy.coordinates import Latitude
from astropy.units import Quantity
from ska_oso_pdm import CoordinateKind, Target, TelescopeType

from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.common.static.constants import (
    LOW_LOCATION,
    MID_LOCATION,
    low_minimum_elevation,
    mid_minimum_elevation,
)
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    check_relevant_context_contains,
    validate,
    validator,
)


@validator
def validate_target(target_context: ValidationContext[Target]) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing a Target to be validated
    :return: the collated ValidationIssues resulting from applying each of
            the relevant Target Validators to the Target
    """

    check_relevant_context_contains(["constraints"], target_context)

    if target_context.primary_entity.reference_coordinate.kind in (
        CoordinateKind.TLE,
        CoordinateKind.SPECIAL,
    ):
        return [
            ValidationIssue(
                level=ValidationIssueType.WARNING,
                message="No validation of target visibility is currently performed",
            )
        ]

    validators = [validate_elevation, validate_single_target_pst_beams]

    return validate(target_context, validators)


@validator
def validate_elevation(
    target_context: ValidationContext[Target],
) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing a Target
        to be validated
    :return: a validation error if the target doesn't reach the minimum
            elevation required for Mid
    """
    constraints = target_context.relevant_context["constraints"]
    telescope = target_context.telescope

    if constraints.altitude.min is not None:
        min_elevation = constraints.altitude.min
    elif telescope == TelescopeType.SKA_MID:
        min_elevation = mid_minimum_elevation()
    else:
        min_elevation = low_minimum_elevation()

    max_elevation = _find_max_elevation(target_context.primary_entity, telescope)

    if max_elevation < Latitude(0, unit=u.deg):
        return [ValidationIssue(message="Source never rises above the horizon")]

    if max_elevation < min_elevation:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Maximum elevation ({round(max_elevation.value, 2)} degrees) "
                f"is less than the limit ({min_elevation.to('degree').value} degrees) ",
            )
        ]

    if telescope == TelescopeType.SKA_LOW and max_elevation < Latitude(45, unit=u.deg):
        return [
            ValidationIssue(
                level=ValidationIssueType.WARNING,
                message=f"Maximum elevation ({round(max_elevation.value, 2)} degrees) "
                "is less than 45 degrees - performance may be degraded",
            )
        ]

    return []


@validator
def validate_single_target_pst_beams(
    target_context: ValidationContext[Target],
) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing an SKA-Low Target
        to be validated
    :return: a validation error if the target doesn't rise above the horizon
        if the target has more tied array pulsar timing beams than supported
        by the array assembly
    """
    allowed_number_pst_beams = get_subarray_specific_parameter_from_osd(
        target_context.telescope, target_context.array_assembly, "number_pst_beams"
    )

    number_pst_beams = len(target_context.primary_entity.tied_array_beams.pst_beams)

    if number_pst_beams > allowed_number_pst_beams:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Number of PST beams on target, {number_pst_beams}, "
                f"exceeds allowed {allowed_number_pst_beams} for "
                f"{target_context.array_assembly.value}",
            )
        ]

    return []


def _find_max_elevation(target: Target, telescope: TelescopeType) -> Latitude:
    """
    Finds the maximum elevation of the target at the telescope site, returning
    an angle elevation that's negative if the target never rises above the horizon.
    """

    # if the target is an AltAz target, the elevation is fixed.
    if target.reference_coordinate.kind == CoordinateKind.ALTAZ:
        return Latitude(target.reference_coordinate.el, u.deg)

    location = MID_LOCATION if telescope == TelescopeType.SKA_MID else LOW_LOCATION
    target_sky_coords = target.reference_coordinate.to_sky_coord()
    target_sky_coords_icrs = target_sky_coords.icrs

    return Quantity(90.0, u.deg) - abs(location.lat - target_sky_coords_icrs.dec)
