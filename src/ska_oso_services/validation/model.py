from __future__ import annotations

from enum import Enum
from functools import wraps
from inspect import signature
from typing import Callable, Generic, TypeVar, get_type_hints

from pydantic import Field
from ska_oso_pdm import PdmObject, TelescopeType, ValidationArrayAssembly


from ska_oso_services.common.model import AppModel

T = TypeVar("T", bound=PdmObject)


class ValidationContext(Generic[T], AppModel):
    """
    This models the input to all :func:`~ska_oso_services.validation.model.Validator`
    functions and should provide all information that the Validator requires.
    """

    primary_entity: T
    source_jsonpath: str = Field(
        "$",
        description="The JSONPath of the primary_entity if it is being validated "
        "within a higher-level object",
    )
    relevant_context: dict = Field(
        default_factory=dict,
        description="Any extra objects or information the validator needs",
    )
    telescope: TelescopeType | None = Field(
        None, description="The telescope the primary_entity applies to, if appropriate"
    )
    array_assembly: ValidationArrayAssembly = Field(
        default=ValidationArrayAssembly.AA05,
        description="The array assembly to validate the primary_entity against, if appropriate",
    )


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
        description="Human-readable information on why the primary_entity is invalid",
    )
    field: str = Field(
        "$",
        description="The JSONPath for the specific part of the primary_entity " "that is invalid",
    )
    level: ValidationIssueType = ValidationIssueType.ERROR


Validator = Callable[[ValidationContext[T]], list[ValidationIssue]]
""" The general Validator function type. It should take the entity to validate
    wrapped in a ValidationContext and return a list of ValidationIssues."""


def validator(validator_func: Validator[T]) -> Validator[T]:
    """
    A decorator to mark a :func:`~ska_oso_services.validation.model.Validator`

    This decorator will combine the source_jsonpath from the input ValidationContext
    with any of the Validator output ValidationIssue fields. To handle nested Validator
    calls, the decorator will set the source_jsonpath back to the root before passing
    the ValidationContext to the decorated Validator. Ultimately this means that the
    callers of the Validators only need to worry about setting the source_jsonpath
    at the point the Validator is called, and the appending of nested results is
    handled by this decorator

    :raises ValueError: It will also perform a type check on the Validator signature,
        raising an error if the decorated function does not have the correct parameters
        or type hints.
    """

    _check_validator_signature(validator_func)

    @wraps(validator_func)
    def wrapper(entity_context: ValidationContext[T]) -> list[ValidationIssue]:
        context_without_source = entity_context.model_copy(update={"source_jsonpath": "$"})
        result = validator_func(context_without_source)

        return [
            issue.model_copy(
                update={"field": _combine_jsonpath(entity_context.source_jsonpath, issue.field)}
            )
            for issue in result
        ]

    return wrapper


def validate(
    entity_context: ValidationContext[T], validators: list[Validator[T]]
) -> list[ValidationIssue]:
    """
    Applies a set of validators to an entity and collects any resulting
    ValidationIssues into a single list.
    """
    return [
        validation_issue
        for validator in validators
        for validation_issue in validator(entity_context)
    ]


def check_relevant_context_contains(
    keys: list[str], validation_context: ValidationContext
) -> None:
    """
    Performs a check that the keys are present in the relevant_context

    :raises ValueError: if any of the keys are not present
    """
    missing_keys = [key for key in keys if key not in validation_context.relevant_context]
    if len(missing_keys) > 0:
        raise ValueError(f"ValidationContext is missing relevant_context: {missing_keys}")


def _check_validator_signature(validator_func: Validator[T]) -> None:
    """
    :raises: ValueError if the signature of the input function
        is not correct for a Validator
    """
    validator_func_signature = signature(validator_func)
    type_hints = get_type_hints(validator_func)
    value_error = ValueError(
        "Validator function must accept a single ValidationContext "
        "and return a list[ValidationIssue], with type hints"
    )

    if len(validator_func_signature.parameters) != 1 or len(type_hints) != 2:
        raise value_error

    arg_type = type_hints[next(iter(validator_func_signature.parameters))]
    if "ska_oso_services.validation.model.ValidationContext" not in str(arg_type):
        raise value_error

    if type_hints.get("return") != list[ValidationIssue]:
        raise value_error


def _combine_jsonpath(source_jsonpath: str = "$", validator_field: str = "$") -> str:
    if validator_field == "$":
        return source_jsonpath

    return f"{source_jsonpath}.{validator_field.lstrip('$.')}"
