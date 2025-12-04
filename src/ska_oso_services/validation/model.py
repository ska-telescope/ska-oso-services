from __future__ import annotations

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
    """
    A single validation message that can be tied to a particular field in
    the object being validated. The field should be the JSONPath corresponding
    to the particular section of the object that is invalid.
    """

    message: str = Field(
        description="List of observations associated with the proposal",
    )
    field: str | None = None
    level: ValidationIssueType = ValidationIssueType.ERROR


Validator = Callable[[T], list[ValidationIssue]]
""" The general Validator function type. It should take the item to validate
    and return a list of ValidationIssues."""


def validate(entity: T, validators: list[Validator[T]]) -> list[ValidationIssue]:
    """
    Applies a set of validators to an entity and collects any resulting
    ValidationIssues into a single list.
    """
    return [
        validation_issue
        for validator in validators
        for validation_issue in validator(entity)
    ]


def apply_validation_issues_to_fields(
    field: str, validation_issues: list[ValidationIssue]
) -> list[ValidationIssue]:
    """
    Creates a copy of the input validation_issues with the input field appended to
    any existing field in each issue in the input list.

    This is useful for collecting lower level ValidationIssue in the context of
    validating some higher level object. For example, a Target Validator might return
    a ValidationIssue for the root of the Target so the field would be empty.
    But if this is Validator is applied to a Target within an SBDefinition then
    the field should be the path of the Target within the SBDefinition.
    """
    return [
        issue.model_copy(
            update={"field": field if issue.field is None else f"{field}.{issue.field}"}
        )
        for issue in validation_issues
    ]
