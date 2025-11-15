# pylint: disable=no-member
from typing import Any

import astropy.units as u
from astroplan import Observer
from astropy.coordinates import AltAz, EarthLocation, Latitude
from astropy.time import Time
from ska_oso_pdm import Target

from ska_oso_services.validation.model import (
    ValidationIssue,
    ValidationIssueType,
    ValidationResult,
    Validator,
    validate,
)

LOW_LOCATION = EarthLocation.of_site("SKA Low")
LOW_OBSERVER = Observer(location=LOW_LOCATION)

MID_LOCATION = EarthLocation.of_site("SKA Mid")
MID_OBSERVER = Observer(location=MID_LOCATION)


def validate_mid_target(target: Target) -> ValidationResult:
    return validate(target, MID_TARGET_VALIDATORS)


def validate_low_target(target: Target) -> ValidationResult:
    return validate(target, LOW_TARGET_VALIDATORS)


def validation_mid_elevation(target: Target) -> list[ValidationIssue]:
    max_elevation = _find_max_elevation(target, MID_OBSERVER)

    if max_elevation < Latitude(15, unit=u.deg):
        return [ValidationIssue(message="Source never rises above 15 degrees")]

    return []


def validate_low_elevation(target: Any) -> list[ValidationIssue]:
    max_elevation = _find_max_elevation(target, LOW_OBSERVER)

    if max_elevation < Latitude(0, unit=u.deg):
        return [ValidationIssue(message="Source never rises above the horizon")]

    if max_elevation < Latitude(45, unit=u.deg):
        return [
            ValidationIssue(
                level=ValidationIssueType.WARNING,
                message="Source never reaches an elevation of 45 degrees "
                "- performance may be degraded",
            )
        ]

    return []


def _find_max_elevation(target: Target, observer: Observer) -> Latitude:
    target_sky_coords = target.reference_coordinate.to_sky_coord()
    target_transit_time = observer.target_meridian_transit_time(
        time=Time.now(), target=target_sky_coords, which="next"
    )
    return target_sky_coords.transform_to(
        AltAz(obstime=target_transit_time, location=observer.location),
    ).alt


LOW_TARGET_VALIDATORS: list[Validator[Target]] = [validate_low_elevation]
MID_TARGET_VALIDATORS: list[Validator[Target]] = [validation_mid_elevation]
