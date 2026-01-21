from unittest import mock

from ska_oso_pdm.builders import (
    LowSBDefinitionBuilder,
    MidSBDefinitionBuilder,
    populate_scan_sequences,
)
from ska_oso_pdm.builders.target_builder import MidTargetBuilder, generate_targets

from ska_oso_services.validation.model import ValidationContext, ValidationIssue, validator
from ska_oso_services.validation.sbdefinition import validate_sbdefinition

TEST_VALIDATION_ISSUE = ValidationIssue(message="test invalid result")
VALID_RESULT = []
INVALID_RESULT = [TEST_VALIDATION_ISSUE]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_target")
def test_each_target_is_validated(mock_validate_target):
    mock_validate_target.side_effect = [
        INVALID_RESULT,
        VALID_RESULT,
        INVALID_RESULT,
    ]
    sbd = MidSBDefinitionBuilder(targets=generate_targets(MidTargetBuilder, num_targets=3))

    input_context = ValidationContext(primary_entity=sbd, telescope=sbd.telescope)

    result = validate_sbdefinition(input_context)

    assert result == [
        TEST_VALIDATION_ISSUE,
        TEST_VALIDATION_ISSUE,
    ]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_target")
def test_each_target_has_field_added(mock_validate_target):
    @validator
    def mock_validator(_: ValidationContext) -> list[ValidationIssue]:
        return INVALID_RESULT

    mock_validate_target.side_effect = mock_validator

    sbd = MidSBDefinitionBuilder(targets=generate_targets(MidTargetBuilder, num_targets=3))

    input_context = ValidationContext(primary_entity=sbd, telescope=sbd.telescope)

    result = validate_sbdefinition(input_context)

    assert result == [
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "$.targets.0"}),
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "$.targets.1"}),
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "$.targets.2"}),
    ]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_scan_definition")
@mock.patch("ska_oso_services.validation.sbdefinition.validate_target")
def test_scans_are_validated(mock_validate_target, mock_validate_scan_definition):
    mock_validate_target.return_value = VALID_RESULT
    mock_validate_scan_definition.return_value = INVALID_RESULT
    sbd = LowSBDefinitionBuilder()
    sbd = populate_scan_sequences(sbd, scan_durations=1)

    input_context = ValidationContext(primary_entity=sbd, telescope=sbd.telescope)

    result = validate_sbdefinition(input_context)

    assert result == INVALID_RESULT
