from enum import Enum
from typing import Callable, TypeVar

from pydantic import Field
from ska_oso_pdm import PdmObject

from ska_oso_services.common.model import AppModel

T = TypeVar("T", bound=PdmObject)


class ValidationIssueType(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(AppModel):
    message: str
    field: str | None = None
    level: ValidationIssueType = ValidationIssueType.ERROR


Validator = Callable[[T], list[ValidationIssue]]


class ValidationResult(AppModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)  # rename to issues?


def validate(entity: T, validators: list[Validator[T]]) -> ValidationResult:
    issues = [
        validation_issue
        for validator in validators
        for validation_issue in validator(entity)
    ]
    return validation_result_from_issues(issues)


def apply_validation_result_to_field(
    field: str, validation_result: ValidationResult
) -> ValidationResult:
    """
    TODO
    """
    if validation_result == ValidationResult(valid=True):
        return validation_result

    return ValidationResult(
        valid=False,
        issues=[
            issue.model_copy(update={"field": field})
            for issue in validation_result.issues
        ],
    )


def validation_result_from_issues(
    validation_issues: list[ValidationIssue],
) -> ValidationResult:
    return ValidationResult(valid=not bool(validation_issues), issues=validation_issues)


def combine_validation_results(
    validation_results: list[ValidationResult],
) -> ValidationResult:
    combined_issues = [
        issue for result in validation_results for issue in result.issues
    ]

    return validation_result_from_issues(combined_issues)
