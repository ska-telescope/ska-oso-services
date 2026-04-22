from ska_oso_pdm import SBDefinition, Target, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm.sb_definition import CSPConfiguration, ScanDefinition

from ska_oso_services.validation.constraints import (
    target_is_jupiter_sun_or_moon,
    validate_constraints,
)
from ska_oso_services.validation.csp import validate_csp
from ska_oso_services.validation.mccs import validate_mccs
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    validator,
)
from ska_oso_services.validation.scan import validate_scan_definition
from ska_oso_services.validation.target import validate_target


@validator
def validate_sbdefinition(
    sbd_context: ValidationContext[SBDefinition],
) -> list[ValidationIssue]:
    """
    Applies all relevant Validators to the SBDefinition elements,
    collecting all the results into a single list.

    :param sbd_context: the full SBDefinition to validate
    :return: the collated ValidationIssues resulting from applying all the
                SBDefinition Validators
    """
    sbd = sbd_context.primary_entity

    # for backwards compatibility.
    if not sbd.validate_against:
        if sbd.telescope == TelescopeType.SKA_MID:
            validation_array_assembly = sbd.dish_allocations.selected_subarray_definition
        else:
            validation_array_assembly = sbd.mccs_allocation.selected_subarray_definition

        # but this won't work if it's a custom array, so subbing out for the
        # most permissive array assembly
        if validation_array_assembly == "Custom":
            validation_array_assembly = ValidationArrayAssembly.AA2

    else:
        validation_array_assembly = sbd.validate_against

    target_validation_results = [
        issue
        for index, target in enumerate(sbd.targets)
        for issue in validate_target(
            ValidationContext(
                primary_entity=target,
                source_jsonpath=f"$.targets.{index}",
                telescope=sbd.telescope,
                array_assembly=validation_array_assembly,
            )
        )
    ]

    # observing constraints can truly be optional in an SBD, so
    # only validating if present

    if sbd.observing_constraints is not None:
        constraint_validation_results = validate_constraints(
            ValidationContext(
                primary_entity=sbd.observing_constraints,
                source_jsonpath="$.observing_constraints",
                relevant_context={
                    "targets": sbd.targets,
                    "scan_definitions": _get_scan_sequence(sbd, preserve_subarray_beams=True),
                },
                telescope=sbd.telescope,
                array_assembly=validation_array_assembly,
            )
        )

    # with the exception being if the target is Jupiter, the Sun or Moon
    # as the default observing constraints are not acceptable in this case
    else:
        constraint_validation_results = []
        for target in sbd.targets:
            if target_is_jupiter_sun_or_moon(target):
                constraint_validation_results.append(
                    ValidationIssue(
                        level=ValidationIssueType.ERROR,
                        field="$.observing_constraints",
                        message=f"default scheduling constraints include a {target.name} "
                        "avoidance zone",
                    )
                )

    csp_validation_results = [
        issue
        for index, csp_config in enumerate(sbd.csp_configurations)
        for issue in validate_csp(
            ValidationContext(
                primary_entity=csp_config,
                source_jsonpath=f"$.csp_configurations.{index}",
                telescope=sbd.telescope,
                array_assembly=validation_array_assembly,
            )
        )
    ]

    receptor_validation_results = []
    if sbd.telescope == TelescopeType.SKA_LOW:
        mccs_validation_results = validate_mccs(
            ValidationContext(
                primary_entity=sbd.mccs_allocation,
                source_jsonpath="$.mccs_allocation",
                telescope=sbd.telescope,
                relevant_context={
                    "targets": sbd.targets,
                    "csp_config": sbd.csp_configurations,
                },
                array_assembly=validation_array_assembly,
            )
        )

        receptor_validation_results = mccs_validation_results

    scan_validation_results = []
    for scan in _get_scan_sequence(sbd):
        target, target_index = _lookup_target_for_scan(scan, sbd)
        csp_config, _ = _lookup_csp_configuration_for_scan(scan, sbd)

        # Though technically the validation issue comes from the scan,
        # it makes more sense to surface it to the user as a target issue
        # TODO this will need a bit of a refactor when there is some
        #  new validation that needs to be attached to the scan or csp config
        scan_context = ValidationContext(
            primary_entity=scan,
            source_jsonpath=f"$.targets.{target_index}",
            telescope=sbd.telescope,
            relevant_context={"target": target, "csp_config": csp_config},
            array_assembly=validation_array_assembly,
        )

        scan_validation_results += validate_scan_definition(scan_context)

    return (
        target_validation_results
        + constraint_validation_results
        + receptor_validation_results
        + csp_validation_results
        + scan_validation_results
    )


def _lookup_target_for_scan(scan: ScanDefinition, sbd: SBDefinition) -> tuple[Target, int]:
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


def _get_scan_sequence(
    sbd: SBDefinition, preserve_subarray_beams: bool = False
) -> list[ScanDefinition] | list[list[ScanDefinition]]:
    if sbd.telescope == TelescopeType.SKA_MID:
        return sbd.dish_allocations.scan_sequence

    elif preserve_subarray_beams is True:
        return [
            subarray_beam.scan_sequence for subarray_beam in sbd.mccs_allocation.subarray_beams
        ]

    else:
        return [
            scan
            for subarray_beam in sbd.mccs_allocation.subarray_beams
            for scan in subarray_beam.scan_sequence
        ]
