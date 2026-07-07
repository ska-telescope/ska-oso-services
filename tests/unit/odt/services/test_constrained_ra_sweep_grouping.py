"""Unit tests for constrained_ra_sweep_grouping."""

import pytest
from ska_oso_pdm import ICRSCoordinates, Target

from ska_oso_services.odt.service.target_grouping import (
    ConstrainedRaSweepGrouper,
    DeclinationQueues,
    Pointing,
)

# 8 dec rows (0°, 2°, 4°, …, 14°) × 2 RA columns (0°, 3°) = 16 targets.
# Ordered dec-major: index 0 = (ra=0, dec=0), index 1 = (ra=3, dec=0),
#                    index 2 = (ra=0, dec=2), index 3 = (ra=3, dec=2), …
GRID_16_TARGETS = [
    Target(
        target_id="t-0000",
        name="T0",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+00:00:00.00"),
    ),
    Target(
        target_id="t-0001",
        name="T1",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+00:00:00.00"),
    ),
    Target(
        target_id="t-0002",
        name="T2",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+02:00:00.00"),
    ),
    Target(
        target_id="t-0003",
        name="T3",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+02:00:00.00"),
    ),
    Target(
        target_id="t-0004",
        name="T4",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+04:00:00.00"),
    ),
    Target(
        target_id="t-0005",
        name="T5",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+04:00:00.00"),
    ),
    Target(
        target_id="t-0006",
        name="T6",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+06:00:00.00"),
    ),
    Target(
        target_id="t-0007",
        name="T7",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+06:00:00.00"),
    ),
    Target(
        target_id="t-0008",
        name="T8",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+08:00:00.00"),
    ),
    Target(
        target_id="t-0009",
        name="T9",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+08:00:00.00"),
    ),
    Target(
        target_id="t-0010",
        name="T10",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+10:00:00.00"),
    ),
    Target(
        target_id="t-0011",
        name="T11",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+10:00:00.00"),
    ),
    Target(
        target_id="t-0012",
        name="T12",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+12:00:00.00"),
    ),
    Target(
        target_id="t-0013",
        name="T13",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+12:00:00.00"),
    ),
    Target(
        target_id="t-0014",
        name="T14",
        reference_coordinate=ICRSCoordinates(ra_str="00:00:00.00", dec_str="+14:00:00.00"),
    ),
    Target(
        target_id="t-0015",
        name="T15",
        reference_coordinate=ICRSCoordinates(ra_str="00:12:00.00", dec_str="+14:00:00.00"),
    ),
]

# Subset: first 2 dec rows (4 targets) for small-catalogue test.
GRID_4_TARGETS = GRID_16_TARGETS[:4]


def _attach_fwhm(targets: list[Target]) -> list[Pointing]:
    return [
        Pointing(
            target_id=target.target_id,
            name=target.name,
            reference_coordinate=target.reference_coordinate,
            fwhm_deg=1.0,
        )
        for target in targets
    ]


GRID_16_TARGETS_WITH_FWHM = _attach_fwhm(GRID_16_TARGETS)
GRID_4_TARGETS_WITH_FWHM = _attach_fwhm(GRID_4_TARGETS)


def _group_target_ids(groups: list[list[Target]]) -> list[str]:
    return [target.target_id for group in groups for target in group]


class TestConstrainedRaSweepGrouping:
    """Tests for the ConstrainedRaSweepGrouper.group method."""

    def test_two_interleaved_groups_on_regular_grid(self):
        """A 8-row × 2-column grid should produce exactly two full groups of 8.

        This verifies constrained-RA-sweep still deterministically creates
        two full groups on a regular grid under relative-separation checks.
        """
        grouper = ConstrainedRaSweepGrouper()
        groups = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=8))

        assert len(groups) == 2
        assert all(len(g) == 8 for g in groups)

    def test_full_coverage_no_duplicates(self):
        """Every target id must appear exactly once across all groups."""
        grouper = ConstrainedRaSweepGrouper()
        groups = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=8))

        all_target_ids = _group_target_ids(groups)
        expected_target_ids = [target.target_id for target in GRID_16_TARGETS_WITH_FWHM]
        assert sorted(all_target_ids) == sorted(expected_target_ids)

    def test_group_size_respected(self):
        """No group should exceed the requested group_size."""
        grouper = ConstrainedRaSweepGrouper()
        groups = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=4))

        assert all(len(g) <= 4 for g in groups)
        # All targets must still be covered
        all_target_ids = _group_target_ids(groups)
        expected_target_ids = [target.target_id for target in GRID_16_TARGETS_WITH_FWHM]
        assert sorted(all_target_ids) == sorted(expected_target_ids)

    def test_deterministic(self):
        """Running twice on the same input produces identical groups."""
        grouper = ConstrainedRaSweepGrouper()
        groups_a = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=8))
        groups_b = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=8))

        assert groups_a == groups_b

    def test_small_catalogue_single_partial_group(self):
        """Fewer targets than group_size should yield a single partial group."""
        grouper = ConstrainedRaSweepGrouper()
        groups = list(grouper.group(GRID_4_TARGETS_WITH_FWHM, group_size=8))

        all_target_ids = _group_target_ids(groups)
        expected_target_ids = [target.target_id for target in GRID_4_TARGETS_WITH_FWHM]
        assert sorted(all_target_ids) == sorted(expected_target_ids)

    def test_precomputed_dec_queues(self):
        """ConstrainedRaSweepGrouper accepts pre-computed DeclinationQueues."""
        rd = DeclinationQueues.from_targets(GRID_16_TARGETS_WITH_FWHM)
        grouper = ConstrainedRaSweepGrouper(dec_queues=rd)
        groups = list(grouper.group(GRID_16_TARGETS_WITH_FWHM, group_size=8))

        # Still must cover all targets
        all_target_ids = _group_target_ids(groups)
        expected_target_ids = [target.target_id for target in GRID_16_TARGETS_WITH_FWHM]
        assert sorted(all_target_ids) == sorted(expected_target_ids)


def _make_target(ra_str: str, dec_str: str, idx: int) -> Target:
    """Helper to create a Target with minimal boilerplate."""
    return Target(
        target_id=f"v-{idx:04d}",
        name=f"V{idx}",
        reference_coordinate=ICRSCoordinates(ra_str=ra_str, dec_str=dec_str),
    )


# Non-uniform dec spacing with no missing rings:
# rows at 0°, 2°, 4.05°, 6.05° (gaps: 2.0°, 2.05°, 2.0°).
NON_UNIFORM_DEC_TARGETS = [
    _make_target("00:00:00.00", "+00:00:00.00", 0),
    _make_target("00:12:00.00", "+00:00:00.00", 1),
    _make_target("00:00:00.00", "+02:00:00.00", 2),
    _make_target("00:12:00.00", "+02:00:00.00", 3),
    _make_target("00:00:00.00", "+04:03:00.00", 4),
    _make_target("00:12:00.00", "+04:03:00.00", 5),
    _make_target("00:00:00.00", "+06:03:00.00", 6),
    _make_target("00:12:00.00", "+06:03:00.00", 7),
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


class TestValidateDeclinationQueues:
    """Tests for DeclinationQueues.validate() pre-flight checks."""

    def test_valid_catalogue_passes(self):
        """The regular GRID_16_TARGETS should pass validation without error."""
        rd = DeclinationQueues.from_targets(GRID_16_TARGETS_WITH_FWHM)
        rd.validate()

    def test_non_uniform_dec_raises(self):
        """Catalogue with irregular dec spacing should raise ValueError."""
        rd = DeclinationQueues.from_targets(_attach_fwhm(NON_UNIFORM_DEC_TARGETS))
        with pytest.raises(ValueError, match="Declination spacing is not uniform"):
            rd.validate()

    def test_non_uniform_dec_can_relax_tolerance(self):
        """Callers can override the default declination spacing tolerance."""
        rd = DeclinationQueues.from_targets(_attach_fwhm(NON_UNIFORM_DEC_TARGETS))
        rd.validate(dec_uniformity_tolerance=0.03)

    def test_missing_ring_raises(self):
        """Catalogue with a gap in ring ids should raise ValueError."""
        rd = DeclinationQueues.from_targets(_attach_fwhm(MISSING_RING_TARGETS))
        with pytest.raises(ValueError, match="Empty ring"):
            rd.validate()
