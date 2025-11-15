from unittest import mock

from ska_oso_pdm.builders import LowSBDefinitionBuilder, MidSBDefinitionBuilder
from ska_oso_pdm.builders.target_builder import (
    LowTargetBuilder,
    MidTargetBuilder,
    generate_targets,
)

from ska_oso_services.validation.model import ValidationIssue, ValidationResult
from ska_oso_services.validation.sbdefinition import validate_sbdefinition

TEST_VALIDATION_ISSUE = ValidationIssue(message="test invalid result")
VALID_RESULT = ValidationResult(valid=True, issues=[])
INVALID_RESULT = ValidationResult(valid=False, issues=[TEST_VALIDATION_ISSUE])


class TestMid:

    @mock.patch("ska_oso_services.validation.sbdefinition.validate_mid_target")
    def test_sbdefinition_is_valid(self, mock_validate_mid_target):
        mock_validate_mid_target.side_effect = [
            INVALID_RESULT,
            VALID_RESULT,
            INVALID_RESULT,
        ]
        sbd = MidSBDefinitionBuilder(
            targets=generate_targets(MidTargetBuilder, num_targets=3)
        )

        result = validate_sbdefinition(sbd)

        assert result.valid is False
        assert result.issues == [
            TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.0"}),
            TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.2"}),
        ]


class TestLow:

    @mock.patch("ska_oso_services.validation.sbdefinition.validate_low_target")
    def test_sbdefinition_is_valid(self, mock_validate_low_target):
        mock_validate_low_target.side_effect = [
            VALID_RESULT,
            INVALID_RESULT,
            VALID_RESULT,
        ]
        sbd = LowSBDefinitionBuilder(
            targets=generate_targets(LowTargetBuilder, num_targets=3)
        )

        result = validate_sbdefinition(sbd)

        assert result.valid is False
        assert result.issues == [
            TEST_VALIDATION_ISSUE.model_copy(update={"field": "targets.1"}),
        ]
