import pytest
from ska_oso_pdm import (
    Beam,
    ICRSCoordinates,
    PointingKind,
    PointingPattern,
    SBDefinition,
    SinglePointParameters,
)
from ska_oso_pdm.builders import (
    LowSBDefinitionBuilder,
    MidSBDefinitionBuilder,
    populate_scan_sequences,
)

from ska_oso_services.validation.model import ValidationIssue
from ska_oso_services.validation.scans import validate_scans


class TestTiedArrayBeams:

    @pytest.mark.parametrize(
        "sbd", [MidSBDefinitionBuilder(), LowSBDefinitionBuilder()]
    )
    def test_tied_array_beam_not_within_hpbw(self, sbd):
        TEST_CSP_CONFIG_ID = "csp-configuration-18762"
        sbd.csp_configurations[0].config_id = TEST_CSP_CONFIG_ID
        sbd = populate_scan_sequences(sbd, scan_durations=1)

        sbd.targets[0].tied_array_beams.pst_beams = [
            Beam(
                beam_id=1,
                beam_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.0946", dec_str="+89:15:50.792"
                ),
            )
        ]
        result = validate_scans(sbd)

        assert result == [
            ValidationIssue(
                field="targets.0.tied_array_beams.pst_beams.0",
                message=f"Tied-array beam lies further from the target than half of the the half-power beamwidth for CSP Config {TEST_CSP_CONFIG_ID}",
            )
        ]

    def test_tied_array_beam_not_within_hpbw_for_meerkat_dishes(self):
        sbd = MidSBDefinitionBuilder()
        TEST_CSP_CONFIG_ID = "csp-configuration-18762"
        sbd.csp_configurations[0].config_id = TEST_CSP_CONFIG_ID
        sbd = populate_scan_sequences(sbd, scan_durations=1)

        sbd.targets[0].tied_array_beams.pst_beams = [
            Beam(
                beam_id=1,
                beam_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.0946", dec_str="+89:15:50.792"
                ),
            )
        ]
        result = validate_scans(sbd)

        assert result == [
            ValidationIssue(
                field="targets.0.tied_array_beams.pst_beams.0",
                message=f"Tied-array beam lies further from the target than "
                f"half of the the half-power beamwidth for CSP Config {TEST_CSP_CONFIG_ID}",
            )
        ]

    @pytest.mark.parametrize(
        "sbd", [MidSBDefinitionBuilder(), LowSBDefinitionBuilder()]
    )
    def test_tied_array_beam_with_offsets_not_within_hpbw(self, sbd):
        TEST_CSP_CONFIG_ID = "csp-configuration-18762"
        sbd.csp_configurations[0].config_id = TEST_CSP_CONFIG_ID
        sbd.targets[0].tied_array_beams.pst_beams = [
            Beam(
                beam_id=1,
                beam_coordinate=ICRSCoordinates(
                    ra_str="02:31:49.0946", dec_str="+89:15:50.792"
                ),
            )
        ]
        sbd.targets[0].pointing_pattern = PointingPattern(
            active=PointingKind.SINGLE_POINT,
            parameters=[SinglePointParameters(offset_x_arcsec=5, offset_y_arcsec=5)],
        )
        sbd = populate_scan_sequences(sbd, scan_durations=1)

        result = validate_scans(sbd)

        assert result == [
            ValidationIssue(
                field="targets.0.tied_array_beams.pst_beams.0",
                message=f"Tied-array beam lies further from the target "
                f"than half of the the half-power beamwidth for CSP Config {TEST_CSP_CONFIG_ID}",
            )
        ]
