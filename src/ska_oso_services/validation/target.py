# pylint: disable=no-member
import astropy.units as u
from astropy.coordinates import EarthLocation, Latitude
from astropy.units import Quantity
from ska_oso_pdm import Target, TelescopeType

from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    validate,
    validator,
)

LOW_LOCATION = EarthLocation.of_site("SKA Low")
MID_LOCATION = EarthLocation.of_site("SKA Mid")


@validator
def validate_target(target_context: ValidationContext[Target]) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing a Target to be validated
    :return: the collated ValidationIssues resulting from applying each of
            the relevant Target Validators to the Target
    """

    if target_context.telescope == TelescopeType.SKA_MID:
        validators = [validate_mid_elevation, validate_single_target_pst_beams]
    else:
        validators = [validate_low_elevation, validate_single_target_pst_beams]

    return validate(target_context, validators)


@validator
def validate_mid_elevation(
    target_context: ValidationContext[Target],
) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing an SKA-Mid Target
        to be validated
    :return: a validation error if the target doesn't reach the minimum 15 degrees
            elevation required for Mid
    """
    max_elevation = _find_max_elevation(target_context.primary_entity, TelescopeType.SKA_MID)

    if max_elevation < Latitude(15, unit=u.deg):
        return [ValidationIssue(message="Source never rises above 15 degrees")]

    return []


@validator
def validate_low_elevation(
    target_context: ValidationContext[Target],
) -> list[ValidationIssue]:
    """
    :param target_context: a ValidationContext containing an SKA-Low Target
        to be validated
    :return: a validation error if the target doesn't rise above the horizon;
         a validation warning if the maximum elevation of the target is less
         than 45 degrees
    """
    max_elevation = _find_max_elevation(target_context.primary_entity, TelescopeType.SKA_LOW)

    if max_elevation < Latitude(0, unit=u.deg):
        return [ValidationIssue(message="Source never rises above the horizon")]

    if max_elevation < Latitude(45, unit=u.deg):
        return [
            ValidationIssue(
                level=ValidationIssueType.WARNING,
                message=f"Maximum elevation ({round(max_elevation.value, 2)} degrees) "
                f"is less than 45 degrees - performance may be degraded",
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
    location = MID_LOCATION if telescope == TelescopeType.SKA_MID else LOW_LOCATION
    target_sky_coords = target.reference_coordinate.to_sky_coord()

    return Quantity(90.0, u.deg) - abs(location.lat - target_sky_coords.dec)
