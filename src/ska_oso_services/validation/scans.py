import astropy.units as u
from astropy.constants import c as speed_of_light
from astropy.coordinates import Angle
from astropy.units import Quantity
from ska_oso_pdm import Beam, PointingKind, SBDefinition, Target, TelescopeType
from ska_oso_pdm._shared import PointedMosaicParameters
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition

from ska_oso_services.common.static.constants import (
    LOW_STATION_CHANNEL_WIDTH_MHZ,
    MID_CHANNEL_WIDTH_KHZ, LOW_STATION_DIAMETER_M, MID_DISH_DIAMETER_M
)
from ska_oso_services.validation.model import (
    ValidationIssue,
    Validator,
    apply_validation_issues_to_fields,
    validate,
)


# todo use the full sbd because
def validate_scans(sbd: SBDefinition) -> list[ValidationIssue]:
    if sbd.telescope == TelescopeType.SKA_MID:
        return validate_mid_scans(sbd)
    else:
        return validate_low_scans(sbd)


def validate_mid_scans(sbd: SBDefinition) -> list[ValidationIssue]:
    scan_validation_results = []

    for scan in sbd.dish_allocations.scan_sequence:

        target, target_index = _lookup_target_for_scan(scan, sbd)
        csp_config, _ = _lookup_csp_configuration_for_scan(scan, sbd)

        validation_issues = _validate_tied_array_beam(
            target, csp_config, telescope=TelescopeType.SKA_MID
        )

        scan_validation_results += apply_validation_issues_to_fields(
            field=f"targets.{target_index}", validation_issues=validation_issues
        )

    return scan_validation_results


def validate_low_scans(sbd: SBDefinition) -> list[ValidationIssue]:
    scan_validation_results = []
    for subarray_beam in sbd.mccs_allocation.subarray_beams:
        for scan in subarray_beam.scan_sequence:
            target, target_index = _lookup_target_for_scan(scan, sbd)
            csp_config, _ = _lookup_csp_configuration_for_scan(scan, sbd)

            validation_issues = _validate_tied_array_beam(
                target, csp_config, telescope=TelescopeType.SKA_LOW
            )

            scan_validation_results += apply_validation_issues_to_fields(
                field=f"targets.{target_index}", validation_issues=validation_issues
            )

    return scan_validation_results


def _validate_tied_array_beam(
    target: Target, csp_config: CSPConfiguration, telescope: TelescopeType
) -> list[ValidationIssue]:
    hpbw = _get_hpbw(csp_config, telescope)

    def separation(target: Target, pst_beam: Beam) -> Angle:
        if target.pointing_pattern.active == PointingKind.POINTED_MOSAIC:
            pointing_parameters: PointedMosaicParameters = next(
                p
                for p in target.pointing_pattern.parameters
                if p.kind is PointingKind.POINTED_MOSAIC
            )
            target_sky_coord = (
                target.reference_coordinate.to_sky_coord().spherical_offsets_by(
                    # tied array beams can only have one pointing offset - # todo validate this?
                    d_lon=pointing_parameters.offsets[0].x * u.Unit(pointing_parameters.units),
                    d_lat=pointing_parameters.offsets[0].x * u.Unit(pointing_parameters.units),
                )
            )
        else:
            target_sky_coord = target.reference_coordinate.to_sky_coord()

        pst_beam_sky_coord = pst_beam.beam_coordinate.to_sky_coord()

        return target_sky_coord.separation(pst_beam_sky_coord).to(u.rad)

    return [
        ValidationIssue(
            field=f"tied_array_beams.pst_beams.{index}",
            message=f"Tied-array beam lies further from the target than half of "
                    f"the HPBW for CSP {csp_config.name}",
        )
        for index, pst_beam in enumerate(target.tied_array_beams.pst_beams)
        if separation(target, pst_beam) > (hpbw / 2)
    ]


def _get_hpbw(csp_config: CSPConfiguration, telescope: TelescopeType) -> Angle:
    # calculate hpbw of the dish/station
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
            spw.centre_frequency
            + (MID_CHANNEL_WIDTH_KHZ * 1e3 * spw.number_of_channels / 2)
            for spw in csp_config.midcbf.subbands[0].correlation_spws
        ]

    max_frequency_hz = Quantity(max(band_upper_limits_hz), unit=u.s**-1)

    return ((speed_of_light / max_frequency_hz) / diameter_m) * u.rad


def _lookup_target_for_scan(
    scan: ScanDefinition, sbd: SBDefinition
) -> tuple[Target, int]:
    return next(
        (target, index)
        for index, target in enumerate(sbd.targets)
        if target.target_id == scan.target_ref
    )


def _lookup_csp_configuration_for_scan(
    scan: ScanDefinition, sbd: SBDefinition
) -> tuple[CSPConfiguration, int]:
    return next(
        (csp_config, index)
        for index, csp_config in enumerate(sbd.csp_configurations)
        if csp_config.config_id == scan.csp_configuration_ref
    )


# def validate_mid_scans(scan_definition: ScanDefinition, target: Target, csp_configuration: CSPConfiguration) -> list[ValidationIssue]:
#     return validate((scan_definition, target, csp_configuration), MID_SCAN_VALIDATORS)
#
# def validate_low_scans(scan_definition: ScanDefinition, target: Target, csp_configuration: CSPConfiguration) -> list[ValidationIssue]:
#     return validate((scan_definition, target, csp_configuration), LOW_SCAN_VALIDATORS)


MID_SCAN_VALIDATORS: list[
    Validator[tuple[ScanDefinition, Target, CSPConfiguration]]
] = []
LOW_SCAN_VALIDATORS: list[
    Validator[tuple[ScanDefinition, Target, CSPConfiguration]]
] = []
