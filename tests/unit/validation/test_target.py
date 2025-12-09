import pytest
from ska_oso_pdm import ICRSCoordinates, TelescopeType
from ska_oso_pdm.builders.target_builder import LowTargetBuilder, MidTargetBuilder

from ska_oso_services.validation.model import ValidationContext, ValidationIssueType
from ska_oso_services.validation.target import (
    validate_low_elevation,
    validate_target,
    validation_mid_elevation,
)
from tests.unit.validation import LMC_TARGET


@pytest.mark.parametrize("telescope", [TelescopeType.SKA_MID, TelescopeType.SKA_LOW])
def test_full_target_validation_for_valid_target(telescope):
    result = validate_target(
        ValidationContext(primary_entity=LMC_TARGET, telescope=telescope)
    )
    assert result == []


def test_mid_target_below_min_elevation():
    input_context = ValidationContext(
        primary_entity=MidTargetBuilder(
            name="Polaris",
            reference_coordinate=ICRSCoordinates(
                ra_str="02:31:49.09456", dec_str="+89:15:50.7923"
            ),
        ),
        telescope=TelescopeType.SKA_MID,
    )
    result = validation_mid_elevation(input_context)
    assert result[0].message == "Source never rises above 15 degrees"


def test_low_target_below_horizon():

    input_context = ValidationContext(
        primary_entity=LowTargetBuilder(
            name="JVAS 1938+666",
            reference_coordinate=ICRSCoordinates(
                ra_str="19:38:25.2890", dec_str="+66:48:52.915"
            ),
        ),
        telescope=TelescopeType.SKA_LOW,
    )

    result = validate_low_elevation(input_context)
    assert result[0].message == "Source never rises above the horizon"


def test_low_target_below_min_elevation():
    input_context = ValidationContext(
        primary_entity=LowTargetBuilder(
            name="47 Tuc",
            reference_coordinate=ICRSCoordinates(
                ra_str="00:24:05.3590", dec_str="-72:04:53.200"
            ),
        ),
        telescope=TelescopeType.SKA_LOW,
    )

    result = validate_low_elevation(input_context)

    assert len(result) == 1
    assert (
        result[0].message
        == "Maximum elevation (44.74 degrees) is less than 45 degrees "
        "- performance may be degraded"
    )
    assert result[0].level == ValidationIssueType.WARNING
