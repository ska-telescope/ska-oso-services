# pylint: disable=no-member
import astropy.units as u
from astroplan import Observer
from astropy.coordinates import EarthLocation, Latitude
from astropy.units import Quantity
from ska_oso_pdm import Target, TelescopeType

from ska_oso_services.validation.model import (
    ValidationIssue,
    ValidationIssueType,
    Validator,
    validate,
)

LOW_LOCATION = EarthLocation.of_site("SKA Low")
LOW_OBSERVER = Observer(location=LOW_LOCATION)

MID_LOCATION = EarthLocation.of_site("SKA Mid")
MID_OBSERVER = Observer(location=MID_LOCATION)


def validate_mid_target(target: Target) -> list[ValidationIssue]:
    """
    :param target: a Target intended to be observed by SKA Mid
    :return: the collated ValidationIssues resulting from applying each of the
        :data:`~ska_oso_services.validation.target.MID_TARGET_VALIDATORS` to the target
    """
    return validate(target, MID_TARGET_VALIDATORS)


def validate_low_target(target: Target) -> list[ValidationIssue]:
    """
    :param target: a Target intended to be observed by SKA Low
    :return: the collated ValidationIssues resulting from applying each of
        the :data:`~ska_oso_services.validation.target.LOW_TARGET_VALIDATORS`
        to the target
    """
    return validate(target, LOW_TARGET_VALIDATORS)


def validation_mid_elevation(target: Target) -> list[ValidationIssue]:
    """
    :param target: a Target intended to be observed by SKA Mid
    :return: a validation error if the target doesn't reach the minimum 15 degrees
            elevation required for Mid
    """
    max_elevation = _find_max_elevation(target, TelescopeType.SKA_MID)

    if max_elevation < Latitude(15, unit=u.deg):
        return [ValidationIssue(message="Source never rises above 15 degrees")]

    return []


def validate_low_elevation(target: Target) -> list[ValidationIssue]:
    """
    :param target: a Target intended to be observed by SKA Low
    :return: a validation error if the target doesn't rise above the horizon;
         a validation warning if the maximum elevation of the target is less
         than 45 degrees
    """
    max_elevation = _find_max_elevation(target, TelescopeType.SKA_LOW)

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


def _find_max_elevation(target: Target, telescope: TelescopeType) -> Latitude:
    """
    Finds the maximum elevation of the target at the telescope site, returning
    an angle elevation that's negative if the target never rises above the horizon.
    """
    location = MID_LOCATION if telescope == TelescopeType.SKA_MID else LOW_LOCATION
    target_sky_coords = target.reference_coordinate.to_sky_coord()

    return Quantity(90.0, u.deg) - abs(location.lat - target_sky_coords.dec)


LOW_TARGET_VALIDATORS: list[Validator[Target]] = [validate_low_elevation]
""" The list of :func:`~ska_oso_services.validation.model.Validator` functions to
    be applied to a Target intended to be observed by SKA Low """


MID_TARGET_VALIDATORS: list[Validator[Target]] = [validation_mid_elevation]
""" The list of :func:`~ska_oso_services.validation.model.Validator` functions to
    be applied to a Target intended to be observed by SKA Mid """
