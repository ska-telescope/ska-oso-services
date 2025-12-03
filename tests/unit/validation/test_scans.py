import pytest
from ska_oso_pdm import (
    Beam,
    ICRSCoordinates,
    PointingKind,
    PointingPattern,
    SBDefinition,
)
from ska_oso_pdm._shared import PointedMosaicParameters
from ska_oso_pdm._shared.target import AngleUnits, CoordinatesOffset
from ska_oso_pdm.builders import (
    LowSBDefinitionBuilder,
    MidSBDefinitionBuilder,
    populate_scan_sequences,
)
from ska_oso_pdm.builders.target_builder import MidTargetBuilder

from ska_oso_services.validation.model import ValidationIssue
from ska_oso_services.validation.scans import validate_scans

LMC_TARGET = MidTargetBuilder(
    name="LMC",
    reference_coordinate=ICRSCoordinates(
        ra_str="05:23:34.6000", dec_str="-69:45:22.000"
    ),
)


class TestTiedArrayBeams:

    @pytest.mark.parametrize(
        "sbd", [MidSBDefinitionBuilder(), LowSBDefinitionBuilder()]
    )
    def test_tied_array_beam_not_within_hpbw(self, sbd):
        sbd.targets = [LMC_TARGET]

        sbd.targets[0].tied_array_beams.pst_beams = [
            Beam(
                beam_id=1,
                beam_coordinate=ICRSCoordinates(
                    # PSR J0458−67, which won't be within the beam
                    # for the default CSP setup
                    ra_str="04:58:59.0000",
                    dec_str="-67:43:00.000",
                ),
            )
        ]
        sbd = populate_scan_sequences(sbd, scan_durations=1)
        result = validate_scans(sbd)

        assert result == [
            ValidationIssue(
                field="targets.0.tied_array_beams.pst_beams.0",
                message=f"Tied-array beam lies further from the target than "
                f"half of the HPBW for CSP {sbd.csp_configurations[0].name}",
            )
        ]

    @pytest.mark.parametrize("sbd", [LowSBDefinitionBuilder()])
    def test_tied_array_beam_with_offsets_not_within_hpbw(self, sbd: SBDefinition):
        sbd.targets = [LMC_TARGET]

        sbd.targets[0].tied_array_beams.pst_beams = [
            Beam(
                beam_id=1,
                beam_coordinate=ICRSCoordinates(
                    # PSR J0532-69, which is within the beam if there are no offsets
                    ra_str="05:32:04.0000",
                    dec_str="-69:46:00.000",
                ),
            )
        ]

        sbd = populate_scan_sequences(sbd, scan_durations=1)

        # Sanity check before adding offets
        assert len(validate_scans(sbd)) == 0

        sbd.targets[0].pointing_pattern = PointingPattern(
            active=PointingKind.POINTED_MOSAIC,
            parameters=[
                PointedMosaicParameters(
                    offsets=[CoordinatesOffset(x=-0.2, y=0)], units=AngleUnits.DEGREES
                )
            ],
        )

        result = validate_scans(sbd)

        assert result == [
            ValidationIssue(
                field="targets.0.tied_array_beams.pst_beams.0",
                message=f"Tied-array beam lies further from the target "
                f"than half of the HPBW for CSP {sbd.csp_configurations[0].name}",
            )
        ]
