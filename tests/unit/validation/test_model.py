# pylint: disable=unused-argument
import pytest
from ska_oso_pdm import TelescopeType
from ska_oso_pdm.builders import MidSBDefinitionBuilder

from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    check_relevant_context_contains,
    validate,
    validator,
)

TEST_VALIDATION_ISSUE_WITH_FIELD = ValidationIssue(
    message="test invalid result", field="an.invalid.field"
)


@validator
def mock_validator(_: ValidationContext) -> list[ValidationIssue]:
    return [TEST_VALIDATION_ISSUE_WITH_FIELD]


def test_validate_combines_results():
    input_context = ValidationContext(
        primary_entity=MidSBDefinitionBuilder(), telescope=TelescopeType.SKA_MID
    )

    mock_validators = [
        lambda _: [TEST_VALIDATION_ISSUE_WITH_FIELD, TEST_VALIDATION_ISSUE_WITH_FIELD],
        lambda _: [TEST_VALIDATION_ISSUE_WITH_FIELD],
    ]

    result = validate(input_context, mock_validators)

    assert len(result) == 3


def test_decorator_checks_type():

    expected_error_msg = (
        "Validator function must accept a single ValidationContext "
        "and return a list[ValidationIssue]"
    )

    with pytest.raises(ValueError) as excinfo:

        @validator
        def not_a_real_validator(x) -> list[ValidationIssue]:
            return []

    assert expected_error_msg in str(excinfo)

    with pytest.raises(ValueError) as excinfo:

        @validator
        def not_a_real_validator_again(x: str) -> list[ValidationIssue]:
            return []

    assert expected_error_msg in str(excinfo)

    with pytest.raises(ValueError) as excinfo:

        @validator
        def not_a_real_validator_again_again(x: ValidationContext[str]) -> str:
            return "not a ValidationIssue"

    assert expected_error_msg in str(excinfo)


def test_decorator_appends_source():

    test_source_jsonpath = "$.some.input.path"

    input_context = ValidationContext(
        source_jsonpath=test_source_jsonpath,
        primary_entity=MidSBDefinitionBuilder(),
        telescope=TelescopeType.SKA_MID,
    )

    result = validate(input_context, [mock_validator])

    assert result == [
        TEST_VALIDATION_ISSUE_WITH_FIELD.model_copy(
            update={
                "field": f"{test_source_jsonpath}"
                f".{TEST_VALIDATION_ISSUE_WITH_FIELD.field}"
            }
        ),
    ]


def test_check_relevant_context_contains():

    input_context = ValidationContext(
        relevant_context={"first_context": "some context"},
        primary_entity=MidSBDefinitionBuilder(),
        telescope=TelescopeType.SKA_MID,
    )

    with pytest.raises(ValueError) as excinfo:
        check_relevant_context_contains(
            ["first_context", "second_context"], input_context
        )

    assert "ValidationContext is missing relevant_context: ['second_context']" in str(
        excinfo.value
    )
