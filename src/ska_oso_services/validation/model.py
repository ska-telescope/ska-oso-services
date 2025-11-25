from enum import Enum
from typing import Any, Callable, TypeVar

from pydantic import Field
from ska_oso_pdm import PdmObject

from ska_oso_services.common.model import AppModel

T = TypeVar("T", bound=PdmObject | tuple)


class ValidationIssueType(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(AppModel):
    message: str
    field: str | None = None
    level: ValidationIssueType = ValidationIssueType.ERROR


Validator = Callable[[T], list[ValidationIssue]]


def validate(entity: T, validators: list[Validator[T]]) -> list[ValidationIssue]:
    return [
        validation_issue
        for validator in validators
        for validation_issue in validator(entity)
    ]


def apply_validation_issues_to_fields(
    field: str, validation_issues: list[ValidationIssue]
) -> list[ValidationIssue]:
    """
    TODO
    """
    return [
        issue.model_copy(
            update={"field": field if issue.field is None else f"{field}.{issue.field}"}
        )
        for issue in validation_issues
    ]
