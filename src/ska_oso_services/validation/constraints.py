# pylint: disable=no-member
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
)
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    check_relevant_context_contains,
    validator,
)


@dataclass
class TargetLSTConstraints:
    target: Target
    lst_constraint: LSTConstraint


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

    constraints = constraints_context.primary_entity

    for target in targets:
        if target.reference_coordinate.kind == CoordinateKind.SPECIAL:
            if sso_has_an_incompatible_constraint(target.reference_coordinate, constraints):
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


def sso_has_an_incompatible_constraint(
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
        return getattr(constraints, attr_name, None) is not None

    return False


def calculate_elevation_implied_from_lst_constraint(
    telescope: TelescopeType, target: Target, lst_constraint: LSTConstraint
) -> list[u.Quantity]:
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

    return elevation_from_lst


def create_target_exec_list(
    targets: list[Target],
    scan_definitions: list[ScanDefinition],
    sbd_lst_constraint: LSTConstraint,
) -> list[TargetLSTConstraints]:
    """
    the LST constraint in the SBD is for *starting* the SBD, therefore
    each target has its own LST window during which it must be validated;
    a target that might not have risen when the SBD is executed may well be
    valid when its own scan commences. This function is to create an LSTConstraint
    for each target, based on the window when its scan will be executed
    """
    cumulative_execution_time = 0 * u.ms

    target_lst_constraints_list = []

    for scan in scan_definitions:
        # extracting the target
        target = next(target for target in targets if target.target_id == scan.target_ref)

        # the target's own lst constraint is the sbd lst constraint + cumulative execution time
        # thus far, for the first scan in the SBD the target lst constraint == the sbd
        # lst_constraintthe target must exceed the elevation limit throughout their scan,
        # starting atlst_start + cumulate_run_time and finishing at
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
            end=sbd_lst_constraint.start + cumulative_execution_time_lst,
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
