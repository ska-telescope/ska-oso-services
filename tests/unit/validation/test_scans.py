import pytest
from ska_oso_pdm import (
    Beam,
    ICRSCoordinates,
    PointingKind,
    PointingPattern,
    SBDefinition,
    TelescopeType,
)
from ska_oso_pdm._shared import PointedMosaicParameters
from ska_oso_pdm._shared.target import AngleUnits, CoordinatesOffset
from ska_oso_pdm.builders import (
    LowSBDefinitionBuilder,
    MidSBDefinitionBuilder,
    populate_scan_sequences,
)
from ska_oso_pdm.sb_definition import ScanDefinition

from ska_oso_services.validation.model import ValidationContext, ValidationIssue
from ska_oso_services.validation.sbdefinition import (
    _lookup_csp_configuration_for_scan,
    _lookup_target_for_scan,
)
from ska_oso_services.validation.scan import (
    validate_scan_definition,
    validate_tied_array_beam_within_hpbw,
)
from tests.unit.validation import LMC_TARGET


@pytest.mark.parametrize(
    "sbd",
    [
        MidSBDefinitionBuilder(targets=[LMC_TARGET]),
        LowSBDefinitionBuilder(targets=[LMC_TARGET]),
    ],
)
def test_full_scan_definition_validation_for_valid_scan_definition(sbd):
    sbd = populate_scan_sequences(sbd, scan_durations=1)

    input_context = _validation_context_for_first_scan(sbd)

    result = validate_scan_definition(input_context)
    assert result == []


def test_scan_definition_validation_requires_relevant_context():
    sbd = MidSBDefinitionBuilder(targets=[LMC_TARGET])
    sbd = populate_scan_sequences(sbd, scan_durations=1)
    input_context = ValidationContext(
        primary_entity=sbd.dish_allocations.scan_sequence[0], telescope=sbd.telescope
    )

    with pytest.raises(ValueError) as excinfo:
        validate_scan_definition(input_context)

    assert "ValidationContext is missing relevant_context: ['target', 'csp_config']" in str(
        excinfo.value
    )


def test_tied_array_beam_not_within_hpbw():
    sbd = LowSBDefinitionBuilder()
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

    input_context = _validation_context_for_first_scan(sbd)

    result = validate_tied_array_beam_within_hpbw(input_context)

    assert result == [
        ValidationIssue(
            field="$.tied_array_beams.pst_beams.0",
            message=f"Tied-array beam lies further from the target than "
            f"half of the HPBW for CSP {sbd.csp_configurations[0].name}",
        )
    ]


@pytest.mark.parametrize("sbd", [LowSBDefinitionBuilder()])
def test_tied_array_beam_with_offsets_not_within_hpbw(sbd: SBDefinition):
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

    input_context = _validation_context_for_first_scan(sbd)
    # Sanity check before adding offets
    assert len(validate_tied_array_beam_within_hpbw(input_context)) == 0

    sbd.targets[0].pointing_pattern = PointingPattern(
        active=PointingKind.POINTED_MOSAIC,
        parameters=[
            PointedMosaicParameters(
                offsets=[CoordinatesOffset(x=-0.2, y=0)], units=AngleUnits.DEGREES
            )
        ],
    )

    result = validate_tied_array_beam_within_hpbw(input_context)

    assert result == [
        ValidationIssue(
            field="$.tied_array_beams.pst_beams.0",
            message=f"Tied-array beam lies further from the target "
            f"than half of the HPBW for CSP {sbd.csp_configurations[0].name}",
        )
    ]


def _validation_context_for_first_scan(
    sbd: SBDefinition,
) -> ValidationContext[ScanDefinition]:
    if sbd.telescope == TelescopeType.SKA_MID:
        scan_sequence = sbd.dish_allocations.scan_sequence
    else:
        scan_sequence = sbd.mccs_allocation.subarray_beams[0].scan_sequence

    scan = scan_sequence[0]
    target, _ = _lookup_target_for_scan(scan, sbd)
    csp_config, _ = _lookup_csp_configuration_for_scan(scan, sbd)

    return ValidationContext(
        primary_entity=scan_sequence[0],
        telescope=sbd.telescope,
        relevant_context={"target": target, "csp_config": csp_config},
    )
