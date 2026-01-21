# https://stackoverflow.com/a/50099819
# pylint: disable=no-member,no-name-in-module
import astropy.units as u
from astropy.constants import c as speed_of_light
from astropy.coordinates import Angle
from astropy.units import Quantity
from ska_oso_pdm import Beam, PointingKind, Target, TelescopeType
from ska_oso_pdm._shared import PointedMosaicParameters
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition

from ska_oso_services.common.static.constants import (
    LOW_STATION_CHANNEL_WIDTH_MHZ,
    LOW_STATION_DIAMETER_M,
    MID_CHANNEL_WIDTH_KHZ,
    MID_DISH_DIAMETER_M,
)
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    check_relevant_context_contains,
    validate,
    validator,
)


@validator
def validate_scan_definition(
    scan_definition_context: ValidationContext[ScanDefinition],
) -> list[ValidationIssue]:
    """
    :param scan_definition_context: a ValidationContext containing a ScanDefinition
        to be validated. This should also contain a relevant_context with the target
        and csp_config for the scan
    :return: the collated ValidationIssues resulting from applying each of
            scan Validators to the scan_definition
    """
    check_relevant_context_contains(["target", "csp_config"], scan_definition_context)

    validators = [validate_tied_array_beam_within_hpbw]

    return validate(scan_definition_context, validators)


@validator
def validate_tied_array_beam_within_hpbw(
    scan_definition_context: ValidationContext[ScanDefinition],
) -> list[ValidationIssue]:
    """
    :param scan_definition_context: a ValidationContext containing a
            ScanDefinition to be validated
    :return: a validation error for any of the PST beams that are further than
            half of the half-power beamwidth (HPBW) of the dish or station beam
            for the given source
    """
    csp_config = scan_definition_context.relevant_context["csp_config"]
    target = scan_definition_context.relevant_context["target"]

    hpbw = _calculate_hpbw(csp_config, scan_definition_context.telescope)

    return [
        ValidationIssue(
            field=f"tied_array_beams.pst_beams.{index}",
            message=f"Tied-array beam lies further from the target than half of "
            f"the HPBW for CSP {csp_config.name}",
        )
        for index, pst_beam in enumerate(target.tied_array_beams.pst_beams)
        if _angular_separation(target, pst_beam) > (hpbw / 2)
    ]


def _angular_separation(target: Target, pst_beam: Beam) -> Angle:
    """
    Calculates angular separation between the target coordinates and
    the PST beam coordinate, taking into account offsets if present.
    """
    target_sky_coord = target.reference_coordinate.to_sky_coord()
    if target.pointing_pattern.active == PointingKind.POINTED_MOSAIC:
        pointing_parameters: PointedMosaicParameters = next(
            pointing_parameter
            for pointing_parameter in target.pointing_pattern.parameters
            if pointing_parameter.kind is PointingKind.POINTED_MOSAIC
        )
        target_sky_coord = target_sky_coord.spherical_offsets_by(
            # tied array beams can only have one pointing offset
            # TODO add this kind of validation?
            d_lon=pointing_parameters.offsets[0].x * u.Unit(pointing_parameters.units),
            d_lat=pointing_parameters.offsets[0].y * u.Unit(pointing_parameters.units),
        )

    pst_beam_sky_coord = pst_beam.beam_coordinate.to_sky_coord()

    return target_sky_coord.separation(pst_beam_sky_coord).to(u.rad)


def _calculate_hpbw(csp_config: CSPConfiguration, telescope: TelescopeType) -> Angle:
    """
    Calculates the half-power beamwidth for the dish or station for
    the given CSP configuration

    This finds the maximum frequency in the spectral setup and then uses this
    to calculate an angle with lamda / diameter.
    """
    if telescope == TelescopeType.SKA_LOW:
        diameter_m = Quantity(LOW_STATION_DIAMETER_M, unit=u.m)
        band_upper_limits_hz = [
            spw.centre_frequency
            + (LOW_STATION_CHANNEL_WIDTH_MHZ * 1e6 * spw.number_of_channels / 2)
            for spw in csp_config.lowcbf.correlation_spws
        ]
    else:
        # TODO once Mid supports Meerkdat dishes (and tied array beams!) need to use the
        #  correct dish size here based on the array
        diameter_m = Quantity(MID_DISH_DIAMETER_M, unit=u.m)
        band_upper_limits_hz = [
            spw.centre_frequency + (MID_CHANNEL_WIDTH_KHZ * 1e3 * spw.number_of_channels / 2)
            for spw in csp_config.midcbf.subbands[0].correlation_spws
        ]

    max_frequency_hz = Quantity(max(band_upper_limits_hz), unit=u.s**-1)

    return ((speed_of_light / max_frequency_hz) / diameter_m) * u.rad
