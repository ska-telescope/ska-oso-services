# pylint: disable=no-member
import copy
from dataclasses import dataclass

import numpy as np
from astropy import units as u
from ska_oso_pdm import (
    CoordinateKind,
    FivePointParameters,
    SinglePointParameters,
    SolarSystemObjectName,
    SpecialCoordinates,
    Target,
    TelescopeType,
)
from ska_oso_pdm._shared import PointedMosaicParameters
from ska_oso_pdm.sb_definition import LSTConstraint, ObservingConstraints, ScanDefinition

from ska_oso_services.common.static.constants import (
    LOW_LOCATION,
    MID_LOCATION,
    SOLAR_TO_SIDEREAL_CONVERSION_FACTOR,
    low_maximum_elevation,
    low_minimum_elevation,
    mid_maximum_elevation,
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


@dataclass
class TargetLSTConstraints:
    target: Target
    lst_constraint: LSTConstraint


@dataclass
class TargetElevation:
    min: u.Quantity
    max: u.Quantity
    mid: u.Quantity


@validator
def validate_constraints(
    constraints_context: ValidationContext[ObservingConstraints],
) -> list[ValidationIssue]:
    """
    param constraints_context: a ValidationContext containing ObserveringConstraints
        object to be validated
    return: the collated list of ValidationIssues resulting from applying each of the
        relevant ObservingConstraints validators
    """
    if hasattr(constraints_context.primary_entity, "lst"):
        validators = (
            validate_icrs_galactic_target_elevation_limits_are_within_their_lst_constraint,
            validate_sso_targets_do_not_have_separation_constraints,
        )
    else:
        validators = (validate_sso_targets_do_not_have_separation_constraints,)

    return validate(constraints_context, validators)


@validator
def validate_icrs_galactic_target_elevation_limits_are_within_their_lst_constraint(
    constraints_context: ValidationContext,
) -> list[ValidationIssue]:
    """
    function to check that the targets in the scans have an elevation
    above the limit set in the constraints throughout their individual LST
     windows

    :param constraints_context:a ValidationContext containing an Observing
        Constraint to be validated
    :return: a list of validation issues if the targets exceed the elevation
        limits
    """

    check_relevant_context_contains(["targets", "scan_definitions"], constraints_context)
    targets = constraints_context.relevant_context["targets"]
    scan_definitions = constraints_context.relevant_context["scan_definitions"]

    constraints = copy.copy(constraints_context.primary_entity)

    # in theory, it's possible the elevation constraint might have
    # a max but no min or a min but no max. Pulling from OSD if
    # only one is set

    if getattr(constraints.altitude, "max", None) is None:
        constraints.altitude.max = (
            mid_maximum_elevation()
            if constraints_context.telescope == TelescopeType.SKA_MID
            else low_maximum_elevation()
        )

    if getattr(constraints.altitude, "min", None) is None:
        constraints.altitude.min = (
            mid_minimum_elevation()
            if constraints_context.telescope == TelescopeType.SKA_MID
            else low_minimum_elevation()
        )

    target_lst_constraints = create_target_lst_list(
        targets,
        scan_definitions,
        constraints.lst,
    )

    validation_issues = []

    for target_lst_constraint in target_lst_constraints:
        # this is only for Galactic or ICRS targets
        target = target_lst_constraint.target
        if target.reference_coordinate.kind in (CoordinateKind.ICRS, CoordinateKind.GALACTIC):

            target_elevation = calculate_elevation_implied_from_lst_constraint(
                constraints_context.telescope,
                target_lst_constraint.target,
                target_lst_constraint.lst_constraint,
            )

            if (
                target_elevation.min < constraints.altitude.min
                or target_elevation.max > constraints.altitude.max
            ) or target_elevation.mid < 0:
                validation_issues.append(
                    ValidationIssue(
                        level=ValidationIssueType.ERROR,
                        message="Elevation and LST constraints are incompatible "
                        f"for target {target.name}",
                    )
                )

    return validation_issues


@validator
def validate_sso_targets_do_not_have_separation_constraints(
    constraints_context: ValidationContext[ObservingConstraints],
) -> list[ValidationIssue]:
    """
    function to check that e.g. an observation of Jupiter does not
    have a jupiter separation constraint

    :param constraints_context:a ValidationContext containing an Observing
        Constraint to be validated
    :return: a list of validation issues if the targets and separation constraints
        are incompatible
    """

    check_relevant_context_contains(["targets", "scan_definitions"], constraints_context)
    targets = constraints_context.relevant_context["targets"]
    scan_definitions = constraints_context.relevant_context["scan_definitions"]

    constraints = constraints_context.primary_entity

    for scan in scan_definitions:
        # extracting the target
        target = next(target for target in targets if target.target_id == scan.target_ref)
        if target_is_jupiter_sun_or_moon(target) and has_an_incompatible_constraint(
            target.reference_coordinate, constraints
        ):
            return [
                ValidationIssue(
                    level=ValidationIssueType.ERROR,
                    message="cannot specify "
                    f"{target.reference_coordinate.name.value}_separation "
                    f"for a Scheduling Block with {target.reference_coordinate.name} "
                    "as a target",
                )
            ]

        return []


def has_an_incompatible_constraint(
    coordinate: SpecialCoordinates, constraints: ObservingConstraints
) -> bool:
    sso_name = coordinate.name.lower()
    attr_name = f"{sso_name}_separation"

    objects_with_potential_separations = [
        SolarSystemObjectName.SUN,
        SolarSystemObjectName.MOON,
        SolarSystemObjectName.JUPITER,
    ]

    if coordinate.name in objects_with_potential_separations:
        return getattr(constraints, attr_name).min is not None

    return False


def calculate_elevation_implied_from_lst_constraint(
    telescope: TelescopeType, target: Target, lst_constraint: LSTConstraint
) -> TargetElevation:
    """
    private function to calculate the altitude of a target at a given hourangle and telescope
    """
    match telescope:
        case TelescopeType.SKA_LOW:
            latitude = LOW_LOCATION.lat
        case TelescopeType.SKA_MID:
            latitude = MID_LOCATION.lat
        case _:
            raise ValueError(f"Telescope {telescope} not supported")

    latitude_radians = float(latitude.to(u.rad).value)

    target_skycoord = target.reference_coordinate.to_sky_coord()

    declination_radian = float(target_skycoord.icrs.dec.to(u.rad).value)

    # an HA constraint can be implied from the target R.A. and LST constraint

    hourangle_constraint_radian = [
        (lst - target_skycoord.icrs.ra).to(u.rad)
        for lst in [lst_constraint.start, lst_constraint.end]
    ]

    elevation_from_lst = [
        np.arcsin(
            np.sin(latitude_radians) * np.sin(declination_radian)
            + np.cos(latitude_radians) * np.cos(declination_radian) * np.cos(hourangle_radian)
        )
        for hourangle_radian in hourangle_constraint_radian
    ]

    elevation_mid_scan = np.arcsin(
        np.sin(latitude_radians) * np.sin(declination_radian)
        + np.cos(latitude_radians)
        * np.cos(declination_radian)
        * np.cos(sum(hourangle_constraint_radian) / 2.0)
    )

    target_elevation = TargetElevation(
        min=min(elevation_from_lst), max=max(elevation_from_lst), mid=elevation_mid_scan
    )

    return target_elevation


def create_target_lst_list(
    targets: list[Target],
    scan_definitions: list[ScanDefinition] | list[list[ScanDefinition]],
    sbd_lst_constraint: LSTConstraint,
) -> list[TargetLSTConstraints]:
    """
    the LST constraint in the SBD is for *starting* the SBD, therefore
    each target has its own LST window during which it must be validated;
    a target that might not have risen when the SBD is executed may well be
    valid when its own scan commences. This function is to create an LSTConstraint
    for each target, based on the window when its scan will be executed
    """
    # the scan definitions passed to this function could either be a list of
    # ScanDefinitions (if the SBD is for MID or LOW with 1 subarray beam) OR
    # a list of lists of ScanDefinitions. If the former, we want to manipulate
    # it to the latter.

    if isinstance(scan_definitions[0], ScanDefinition):
        scan_definitions = [scan_definitions]

    target_lst_constraints_list = []

    for scans in scan_definitions:
        cumulative_execution_time = 0 * u.ms

        for scan in scans:
            # extracting the target
            target = next(target for target in targets if target.target_id == scan.target_ref)

            # the target's own lst constraint is the sbd lst constraint + cumulative execution time
            # thus far, for the first scan in the SBD the target lst constraint == the sbd
            # lst_constraint the target must exceed the elevation limit throughout their scan,
            # starting at lst_start + cumulate_run_time and finishing at
            # lst_end + cumulative_run_time first converting the cumulative run time from
            # "normal" solar time to sidereal time

            cumulative_execution_time_lst = (
                cumulative_execution_time * SOLAR_TO_SIDEREAL_CONVERSION_FACTOR
            )

            # this can now be directly added to lst constraint. Sadly, Astropy can't handle
            # this for us so we fudge

            cumulative_execution_time_lst = (
                cumulative_execution_time_lst.to(u.hour).value * u.hourangle
            )

            # creating the target specific LSTConstraint Object

            target_lst_constraint = LSTConstraint(
                start=sbd_lst_constraint.start + cumulative_execution_time_lst,
                end=sbd_lst_constraint.end + cumulative_execution_time_lst,
            )

            target_lst_constraints_list.append(
                TargetLSTConstraints(
                    target=target,
                    lst_constraint=target_lst_constraint,
                )
            )

            # now updating the cumulative execution time - should this be done in
            # lst? This feels more obvious and readable. # In future we should
            # factor in for the slew time of mid and perhaps the time it takes to
            # assign resources etc. but for now just considering the scan durations

            pointing_parameters = target.pointing_pattern.parameters[0]
            # getting the pointing pattern
            match pointing_parameters:
                case PointedMosaicParameters():
                    n_scans = len(pointing_parameters.offsets)
                case FivePointParameters():
                    n_scans = 5
                case SinglePointParameters():
                    n_scans = 1
                case _:
                    raise ValueError(
                        f"pointing pattern {pointing_parameters.kind.value} not supported"
                    )

            # calculating the total scan duration and adding to the cumulative execution time

            cumulative_execution_time += scan.scan_duration * n_scans

    return target_lst_constraints_list


def target_is_jupiter_sun_or_moon(target: Target) -> bool:
    if target.reference_coordinate.kind == CoordinateKind.SPECIAL:
        if target.reference_coordinate.name in (
            SolarSystemObjectName.SUN,
            SolarSystemObjectName.MOON,
            SolarSystemObjectName.JUPITER,
        ):
            return True

    return False
