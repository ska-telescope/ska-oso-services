from ska_oso_pdm import ICRSCoordinates
from ska_oso_pdm.builders.target_builder import LowTargetBuilder, MidTargetBuilder

from ska_oso_services.validation.model import ValidationIssueType
from ska_oso_services.validation.target import validate_low_target, validate_mid_target


class TestMid:

    def test_target_is_valid(self):
        result = validate_mid_target(MidTargetBuilder())
        assert result.valid is True

    def test_target_below_min_elevation(self):
        result = validate_mid_target(
            MidTargetBuilder(
                name="Polaris",
                reference_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.09456", dec_str="+89:15:50.7923"
                ),
            )
        )
        assert result.valid is False
        assert result.issues[0].message == "Source never rises above 15 degrees"


class TestLow:
    def test_target_is_valid(self):
        result = validate_low_target(LowTargetBuilder())
        assert result.valid is True

    def test_target_below_horizon(self):
        result = validate_low_target(
            LowTargetBuilder(
                name="Polaris",
                reference_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.09456", dec_str="+89:15:50.7923"
                ),
            )
        )
        assert result.valid is False
        assert result.issues[0].message == "Source never rises above the horizon"

    def test_target_below_min_elevation(self):
        result = validate_low_target(
            LowTargetBuilder(
                name="Polaris",
                reference_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.09456", dec_str="+89:15:50.7923"
                ),
            )
        )
        assert result.valid is False
        assert (
            result.issues[0].message
            == "Source never reaches an elevation of 45 degrees "
            "- performance may be degraded"
        )
        assert result.issues[0].level == ValidationIssueType.WARNING
