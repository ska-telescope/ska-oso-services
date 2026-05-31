"""Unit tests for ring_buffer_grouping."""

import pytest
from ska_oso_pdm import ICRSCoordinates, Target

from ska_oso_services.odt.service.gsm_survey_sbd_generator import (
    RingData,
    ring_buffer_grouping,
)

# 8 dec rows (0°, 2°, 4°, …, 14°) × 2 RA columns (0°, 3°) = 16 targets.
# Ordered dec-major: index 0 = (ra=0, dec=0), index 1 = (ra=3, dec=0),
#                    index 2 = (ra=0, dec=2), index 3 = (ra=3, dec=2), …
GRID_16_TARGETS = [
    Target(target_id="t-0000", name="T0", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+00:00:00.00")),
    Target(target_id="t-0001", name="T1", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+00:00:00.00")),
    Target(target_id="t-0002", name="T2", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+02:00:00.00")),
    Target(target_id="t-0003", name="T3", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+02:00:00.00")),
    Target(target_id="t-0004", name="T4", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+04:00:00.00")),
    Target(target_id="t-0005", name="T5", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+04:00:00.00")),
    Target(target_id="t-0006", name="T6", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+06:00:00.00")),
    Target(target_id="t-0007", name="T7", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+06:00:00.00")),
    Target(target_id="t-0008", name="T8", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+08:00:00.00")),
    Target(target_id="t-0009", name="T9", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+08:00:00.00")),
    Target(target_id="t-0010", name="T10", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+10:00:00.00")),
    Target(target_id="t-0011", name="T11", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+10:00:00.00")),
    Target(target_id="t-0012", name="T12", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+12:00:00.00")),
    Target(target_id="t-0013", name="T13", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+12:00:00.00")),
    Target(target_id="t-0014", name="T14", reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+14:00:00.00")),
    Target(target_id="t-0015", name="T15", reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+14:00:00.00")),
]

# Subset: first 2 dec rows (4 targets) for small-catalogue test.
GRID_4_TARGETS = GRID_16_TARGETS[:4]


class TestRingBufferGrouping:
    """Tests for the ring_buffer_grouping generator function."""

    def test_two_interleaved_groups_on_regular_grid(self):
        """A 8-row × 2-column grid should produce exactly two full groups of 8.

        With delta_dec=2 and RA gap=3 degrees at the equator:
        - min_separation = 2.4 (same-dec cross-column = 3.0, valid)
        - max_separation = 4.8 (diagonal one-row = 3.6, valid)
        - same-column adjacent rows = 2.0 < min_sep → excluded from same group
        This forces the algorithm to interleave alternate dec rows.
        """
        groups = list(ring_buffer_grouping(GRID_16_TARGETS, group_size=8))

        assert len(groups) == 2
        assert all(len(g) == 8 for g in groups)

    def test_full_coverage_no_duplicates(self):
        """Every target index must appear exactly once across all groups."""
        groups = list(ring_buffer_grouping(GRID_16_TARGETS, group_size=8))

        all_indices = [idx for g in groups for idx in g]
        assert sorted(all_indices) == list(range(len(GRID_16_TARGETS)))

    def test_group_size_respected(self):
        """No group should exceed the requested group_size."""
        groups = list(ring_buffer_grouping(GRID_16_TARGETS, group_size=4))

        assert all(len(g) <= 4 for g in groups)
        # All targets must still be covered
        all_indices = [idx for g in groups for idx in g]
        assert sorted(all_indices) == list(range(len(GRID_16_TARGETS)))

    def test_deterministic(self):
        """Running twice on the same input produces identical groups."""
        groups_a = list(ring_buffer_grouping(GRID_16_TARGETS, group_size=8))
        groups_b = list(ring_buffer_grouping(GRID_16_TARGETS, group_size=8))

        assert groups_a == groups_b

    def test_small_catalogue_single_partial_group(self):
        """Fewer targets than group_size should yield a single partial group."""
        groups = list(ring_buffer_grouping(GRID_4_TARGETS, group_size=8))

        all_indices = [idx for g in groups for idx in g]
        assert sorted(all_indices) == list(range(4))

    def test_custom_separation_factors(self):
        """Custom separation factors are applied correctly."""
        # Tighten max_separation_factor so cross-column same-dec (3.0)
        # exceeds max_sep (2.0 * 1.3 = 2.6). Groups will be smaller.
        groups = list(
            ring_buffer_grouping(GRID_16_TARGETS, group_size=8, max_separation_factor=1.3)
        )

        # Still must cover all targets
        all_indices = [idx for g in groups for idx in g]
        assert sorted(all_indices) == list(range(len(GRID_16_TARGETS)))
        # Groups should be smaller since valid neighbours are restricted
        assert all(len(g) <= 8 for g in groups)
        assert len(groups) > 2


def _make_target(ra_str: str, dec_str: str, idx: int) -> Target:
    """Helper to create a Target with minimal boilerplate."""
    return Target(
        target_id=f"v-{idx:04d}",
        name=f"V{idx}",
        reference_coordinate=ICRSCoordinates(ra_str=ra_str, dec_str=dec_str),
    )


# Non-uniform dec spacing: rows at 0°, 2°, 4°, 10° (gap ratio = 6/2 = 3.0)
NON_UNIFORM_DEC_TARGETS = [
    _make_target("00:00:00.00", "+00:00:00.00", 0),
    _make_target("00:12:00.00", "+00:00:00.00", 1),
    _make_target("00:00:00.00", "+02:00:00.00", 2),
    _make_target("00:12:00.00", "+02:00:00.00", 3),
    _make_target("00:00:00.00", "+04:00:00.00", 4),
    _make_target("00:12:00.00", "+04:00:00.00", 5),
    _make_target("00:00:00.00", "+10:00:00.00", 6),
    _make_target("00:12:00.00", "+10:00:00.00", 7),
]

# Missing ring: rows at dec 0°, 2°, 6° — ring_id 2 (dec≈4°) is absent.
MISSING_RING_TARGETS = [
    _make_target("00:00:00.00", "+00:00:00.00", 0),
    _make_target("00:12:00.00", "+00:00:00.00", 1),
    _make_target("00:00:00.00", "+02:00:00.00", 2),
    _make_target("00:12:00.00", "+02:00:00.00", 3),
    _make_target("00:00:00.00", "+06:00:00.00", 4),
    _make_target("00:12:00.00", "+06:00:00.00", 5),
]

# Bad RA spacing: 4 dec rows × 4 RA columns with RA gap = 10° at equator.
# delta_dec = 2°, min_sep = 2.4°, so k=1 RA sep ≈ 10° >> min_sep (fails k=1 check).
BAD_RA_SPACING_TARGETS = [
    _make_target(f"{ra_h:02d}:00:00.00", f"+{dec:02d}:00:00.00", i)
    for i, (ra_h, dec) in enumerate(
        (ra_h, dec) for dec in (0, 2, 4, 6) for ra_h in (0, 1, 2, 3)
    )
]


class TestValidateRingCatalogue:
    """Tests for RingData.validate() pre-flight checks."""

    def test_valid_catalogue_passes(self):
        """The regular GRID_16_TARGETS should pass validation without error."""
        rd = RingData.from_targets(GRID_16_TARGETS)
        rd.validate()

    def test_non_uniform_dec_raises(self):
        """Catalogue with irregular dec spacing should raise ValueError."""
        rd = RingData.from_targets(NON_UNIFORM_DEC_TARGETS)
        with pytest.raises(ValueError, match="Declination spacing is not uniform"):
            rd.validate()

    def test_missing_ring_raises(self):
        """Catalogue with a gap in ring ids should raise ValueError."""
        rd = RingData.from_targets(MISSING_RING_TARGETS)
        # Relax dec-uniformity tolerance so the empty-ring check is reached.
        with pytest.raises(ValueError, match="Empty ring"):
            rd.validate(dec_uniformity_tolerance=3.0)

    def test_bad_ra_spacing_raises(self):
        """Catalogue where RA spacing violates k=1/k=2/k=3 rules raises ValueError."""
        rd = RingData.from_targets(BAD_RA_SPACING_TARGETS)
        with pytest.raises(ValueError, match="RA spacing check failed"):
            rd.validate()
