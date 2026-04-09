from astropy import units as u
from ska_oso_pdm import Target, TelescopeType

import numpy as np

from ska_oso_pdm.sb_definition import ObservingConstraints

from ska_oso_services.common.static.constants import LOW_LOCATION, MID_LOCATION

from ska_oso_services.validation.model import ValidationContext, ValidationIssue

# def validate_lst_and_elevation_constraints_are_compatible(
#         constraints_context: ValidationContext[ObservingConstraints]
# ) -> list[ValidationIssue]:
#     """
#     :param constraints_context: a ValidationContext containing an ObservingConstraints
#         to be validated
#     :return: a list of ValidationIssue objects if the lst constraints and elevations
#         constraints are incompatible
#     """


def calculate_altitude_from_hourangle(
    telescope: TelescopeType, target: Target, hourangle: u.Quantity
) -> u.Quantity:
    """
    private function to calculate the altitude of a target at a given hourangle and telescope
    """
    if telescope == TelescopeType.SKA_LOW:
        latitude = LOW_LOCATION.lat
    else:
        latitude = MID_LOCATION.lat

    latitude_radians = float(latitude.to('radian').value)

    target_skycoord = target.reference_coordinate.to_sky_coord()

    declination_radian = float(target_skycoord.icrs.dec.to('radian').value)

    hourangle_radian = float(hourangle.to('radian').value)

    altitude = np.arcsin(
        np.sin(latitude_radians) * np.sin(declination_radian) +
        np.cos(latitude_radians) * np.cos(declination_radian) * np.cos(hourangle_radian)
    )

    return u.Quantity(altitude, "radian")











