# pylint: disable=no-member
import astropy.units as u
import pytest
from ska_oso_pdm import (
    ICRSCoordinates,
    SolarSystemObjectName,
    SpecialCoordinates,
    Target,
    TelescopeType,
)
from ska_oso_pdm.sb_definition import (
    AngularSeparationConstraint,
    LSTConstraint,
    ObservingConstraints,
)

from ska_oso_services.common.static.constants import LOW_LOCATION
from ska_oso_services.validation.constraints import (
    calculate_elevation_implied_from_lst_constraint,
    sso_has_an_incompatible_constraint,
    validate_icrs_galactic_target_elevation_limits_are_within_their_lst_constraint,
)
from ska_oso_services.validation.model import ValidationContext


def test_validate_targets_lst_and_elevation_constraint(
    mid_multiple_targets_with_observing_constraints_valid,
):
    sbd = mid_multiple_targets_with_observing_constraints_valid
    results = validate_icrs_galactic_target_elevation_limits_are_within_their_lst_constraint(
        ValidationContext(
            primary_entity=sbd.observing_constraints,
            relevant_context={
                "targets": sbd.targets,
                "scan_definitions": sbd.dish_allocations.scan_sequence,
            },
            telescope=sbd.telescope,
        )
    )
    assert results == []


def test_validate_targets_lst_and_elevation_constraint_invalid_sbd(
    mid_multiple_targets_with_observing_constraints_invalid,
):
    sbd = mid_multiple_targets_with_observing_constraints_invalid
    results = validate_icrs_galactic_target_elevation_limits_are_within_their_lst_constraint(
        ValidationContext(
            primary_entity=sbd.observing_constraints,
            relevant_context={
                "targets": sbd.targets,
                "scan_definitions": sbd.dish_allocations.scan_sequence,
            },
            telescope=sbd.telescope,
        )
    )
    assert len(results) == 1
    assert "M15" in results[0].message


def test_sso_has_an_incompatible_constraint():
    constraints = ObservingConstraints(
        moon_separation=AngularSeparationConstraint(min=15.0 * u.deg)
    )
    moon = SpecialCoordinates(name="Moon")
    sun = SpecialCoordinates(name=SolarSystemObjectName.SUN)

    assert sso_has_an_incompatible_constraint(moon, constraints) is True
    assert sso_has_an_incompatible_constraint(sun, constraints) is False


def test_calculate_elevation_implied_from_lst_constraint():
    """
    a target with a declination equal to the latitude of the observatory will have an altitude
    of 90 degrees (i.e. will be directly overhead) when the hourangle == it's R.A. in the below
    example - the lst_constraint.end is 01:00:00 which is the same as the dummy R.A. an hour before
    i.e. the start time corresponds to ~15 degrees, i.e. an elevation of ~90-15 = 75 degrees.
    """

    fake_target_at_low_zenith = Target(
        target_id="target2-34567",
        name="not a real target",
        reference_coordinate=ICRSCoordinates(
            ra_str="01:00:0.00",
            dec_str=str(LOW_LOCATION.lat.to_string(sep=":")),
        ),
    )

    lst_constraint = LSTConstraint(start=0.0 * u.hourangle, end=1.0 * u.hourangle)

    low_altitude_range = calculate_elevation_implied_from_lst_constraint(
        TelescopeType.SKA_LOW, fake_target_at_low_zenith, lst_constraint
    )

    mid_altitude_range = calculate_elevation_implied_from_lst_constraint(
        TelescopeType.SKA_MID, fake_target_at_low_zenith, lst_constraint
    )

    # assert target is exactly overhead when HA == RA (i.e. the end)

    assert low_altitude_range[1].to(u.deg) == u.Quantity(90.0, "degree")

    # assert target is approximate 15 degrees off 90.0 at HA = RA - 1.0

    assert (
        pytest.approx(float(low_altitude_range[0].to(u.deg).value), rel=0.025)
        == u.Quantity(75.0, "degree").value
    )

    # assert that the same source is never at zenith for MID telescope

    assert mid_altitude_range[0].to(u.deg) != u.Quantity(90.0, "degree")  #
    assert mid_altitude_range[1].to(u.deg) != u.Quantity(90.0, "degree")
