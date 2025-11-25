from unittest import mock

from ska_oso_pdm.builders import LowSBDefinitionBuilder, MidSBDefinitionBuilder
from ska_oso_pdm.builders.target_builder import (
    LowTargetBuilder,
    MidTargetBuilder,
    generate_targets,
)

from ska_oso_services.validation.model import ValidationIssue
from ska_oso_services.validation.sbdefinition import validate_sbdefinition

TEST_VALIDATION_ISSUE = ValidationIssue(message="test invalid result")
VALID_RESULT = []
INVALID_RESULT = [TEST_VALIDATION_ISSUE]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_mid_target")
def test_mid_each_target_is_validated_and_field_added(mock_validate_mid_target):
    mock_validate_mid_target.side_effect = [
        INVALID_RESULT,
        VALID_RESULT,
        INVALID_RESULT,
    ]
    sbd = MidSBDefinitionBuilder(
        targets=generate_targets(MidTargetBuilder, num_targets=3)
    )

    result = validate_sbdefinition(sbd)

    assert result == [
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.0"}),
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.2"}),
    ]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_low_target")
def test_low_each_target_is_validated_and_field_added(mock_validate_low_target):
    mock_validate_low_target.side_effect = [
        VALID_RESULT,
        INVALID_RESULT,
        VALID_RESULT,
    ]
    sbd = LowSBDefinitionBuilder(
        targets=generate_targets(LowTargetBuilder, num_targets=3)
    )

    result = validate_sbdefinition(sbd)

    assert result == [
        TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.1"}),
    ]


@mock.patch("ska_oso_services.validation.sbdefinition.validate_scans")
@mock.patch("ska_oso_services.validation.sbdefinition.validate_low_target")
def test_scans_are_validated(mock_validate_low_target, mock_validate_scans):
    mock_validate_low_target.return_value = VALID_RESULT
    mock_validate_scans.return_value = INVALID_RESULT
    sbd = LowSBDefinitionBuilder()

    result = validate_sbdefinition(sbd)

    assert result == INVALID_RESULT
