from ska_oso_pdm import SBDefinition, TelescopeType

from ska_oso_services.validation.model import (
    ValidationResult,
    apply_validation_result_to_field,
    combine_validation_results,
)
from ska_oso_services.validation.target import validate_low_target, validate_mid_target


def validate_sbdefinition(sbd: SBDefinition) -> ValidationResult:
    sbd_is_mid = sbd.telescope == TelescopeType.SKA_MID
    target_validator = validate_mid_target if sbd_is_mid else validate_low_target
    target_validation_results = [
        apply_validation_result_to_field(
            field=f"targets.{index}", validation_result=target_validator(target)
        )
        for index, target in enumerate(sbd.targets)
    ]

    return combine_validation_results(target_validation_results)
