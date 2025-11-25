from astropy.constants import c as speed_of_light
from ska_oso_pdm import SBDefinition, TelescopeType

from ska_oso_services.validation.model import (
    ValidationIssue,
    apply_validation_issues_to_fields,
)
from ska_oso_services.validation.scans import validate_scans
from ska_oso_services.validation.target import validate_low_target, validate_mid_target


def validate_sbdefinition(sbd: SBDefinition) -> list[ValidationIssue]:
    sbd_is_mid = sbd.telescope == TelescopeType.SKA_MID

    target_validator = validate_mid_target if sbd_is_mid else validate_low_target
    target_validation_results = [
        issue
        for index, target in enumerate(sbd.targets)
        for issue in apply_validation_issues_to_fields(
            field=f"targets.{index}", validation_issues=target_validator(target)
        )
    ]

    scan_validation_results = validate_scans(sbd)

    return target_validation_results + scan_validation_results
