# pylint: disable=no-member
from datetime import timedelta
from unittest import mock

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time

from ska_oso_services.odt.service.calibrator_sweep_sbd_generator import generate_cal_sweep_sbd
from ska_oso_services.odt.service.commissioning.generation_utils import Targets
from tests.unit.util import assert_json_is_equal, load_string_from_file

MODULE = "ska_oso_services.odt.service.calibrator_sweep_sbd_generator"

TEST_OBS_START = Time("2026-06-15T10:00:00", scale="utc")


def create_mock_targets(
    primary_name: str = "CalibratorA",
    secondary_names: list[str] | None = None,
) -> Targets:
    """
    Build a deterministic :class:`Targets` namedtuple with one primary
    and zero-or-more secondary entries.
    """
    if secondary_names is None:
        secondary_names = ["CalibratorB", "CalibratorC"]

    def _row(name, ra_deg, dec_deg, s_197):
        t = Table(
            names=["name", "ra_deg", "dec_deg", "s_197"],
            dtype=["U32", "f8", "f8", "f8"],
        )
        t.add_row([name, ra_deg, dec_deg, s_197])
        t["coords"] = SkyCoord(ra=t["ra_deg"] * u.deg, dec=t["dec_deg"] * u.deg)
        return t[0]

    primary = _row(primary_name, 120.0, -30.0, 10.0)

    if not secondary_names:
        return Targets(primary=primary, secondary=None)

    sec_table = Table(
        names=["name", "ra_deg", "dec_deg", "s_197"],
        dtype=["U32", "f8", "f8", "f8"],
    )
    offsets = [(130.0, -25.0, 5.0), (140.0, -20.0, 3.0), (150.0, -15.0, 2.0)]
    for name, (ra, dec, flux) in zip(secondary_names, offsets):
        sec_table.add_row([name, ra, dec, flux])
    sec_table["coords"] = SkyCoord(
        ra=sec_table["ra_deg"] * u.deg, dec=sec_table["dec_deg"] * u.deg
    )

    return Targets(primary=primary, secondary=sec_table)


class TestGenerateCalSweepSBD:
    """Tests for generate_cal_sweep_sbd (basic / VIS mode)."""

    @mock.patch(f"{MODULE}.pick_targets")
    @mock.patch(f"{MODULE}.target_id")
    @mock.patch(f"{MODULE}.csp_configuration_id")
    @mock.patch(f"{MODULE}.scan_definition_id")
    def test_basic_vis_generation(
        self, mock_scan_definition_id, mock_csp_configuration_id, mock_target_id, mock_pick_targets
    ):
        """
        30 min duration with 5 min dwell and 3 targets should produce exactly
        6 scans (2 full cycles of primary + 2 secondaries)
        """
        mock_pick_targets.return_value = create_mock_targets()
        mock_scan_definition_id.side_effect = [
            "scan-00001",
            "scan-00002",
            "scan-00003",
            "scan-00004",
            "scan-00005",
            "scan-00006",
        ]
        mock_csp_configuration_id.return_value = "csp-configuration-00001"
        mock_target_id.side_effect = [
            "target-00001",
            "target-00002",
            "target-00003",
            "target-00004",
            "target-00005",
            "target-00006",
        ]

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=30),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
            interleave_primary=False,
            coarse_channel_start=206,
            coarse_channel_bandwidth=96,
            pst_mode=False,
        )

        sbd.metadata = None
        expected_json = load_string_from_file("expected_cal_sweep_sbd.json")
        assert_json_is_equal(
            sbd.model_dump_json(),
            expected_json,
            exclude_paths=["root['mccs_allocation']['mccs_allocation_id']"],
        )

    @mock.patch(f"{MODULE}.pick_targets")
    def test_scan_count_matches_duration(self, mock_pick_targets):
        """Six 5-min scans fit into 30 min => 6 scan definitions."""
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=30),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        assert len(scans) == 6

    @mock.patch(f"{MODULE}.pick_targets")
    def test_pst_mode_passes_mode_to_pick_targets(self, mock_pick_targets):
        """When pst_mode=True, pick_targets should be called with mode='PST'."""
        mock_pick_targets.return_value = create_mock_targets()

        generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=15),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
            pst_mode=True,
        )

        # Every call to pick_targets should have mode="PST"
        for call in mock_pick_targets.call_args_list:
            assert call.kwargs["mode"] == "PST"

    @mock.patch(f"{MODULE}.pick_targets")
    def test_pst_mode_sets_do_pst_in_csp_configuration(self, mock_pick_targets):
        """CSP configuration should have do_pst=True when pst_mode=True."""
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=15),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
            pst_mode=True,
        )

        assert sbd.csp_configurations[0].lowcbf.do_pst is True


class TestInterleaveMode:

    @mock.patch(f"{MODULE}.pick_targets")
    def test_interleave_adds_primary_between_secondaries(self, mock_pick_targets):
        """
        With interleave_primary=True, the scan sequence should alternate:
        primary, secondary-1, primary, secondary-2, primary, ...
        """
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=60),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
            interleave_primary=True,
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        # First cycle: primary, sec1, primary, sec2, primary = 5 scans = 25 min
        # Second cycle: primary, sec1, primary, sec2, primary = 5 scans = 25 min
        # Third cycle: primary, sec1, primary = 3 scans = 15 min → over 60, only
        # Actually let's just verify the interleave pattern in the first cycle
        target_names = [
            next(t.name for t in sbd.targets if t.target_id == s.target_ref) for s in scans
        ]

        # In the first cycle, after each secondary there should be a primary
        first_cycle = target_names[:5]
        assert first_cycle[0] == "CalibratorA"  # primary
        assert first_cycle[1] == "CalibratorB"  # secondary 1
        assert first_cycle[2] == "CalibratorA"  # interleaved primary
        assert first_cycle[3] == "CalibratorC"  # secondary 2
        assert first_cycle[4] == "CalibratorA"  # interleaved primary

    @mock.patch(f"{MODULE}.pick_targets")
    def test_interleave_time_tracking_is_correct(self, mock_pick_targets):
        """
        Regression: interleave should add primary_dwell (not secondary_dwell)
        to the running total when re-observing the primary.
        """
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=25),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
            interleave_primary=True,
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        # 25 min with 5-min scans and interleaving:
        # primary(5) + sec1(5) + primary(5) + sec2(5) + primary(5) = 25 min → 5 scans
        assert len(scans) == 5


class TestEdgeCases:
    """Tests for edge / boundary cases."""

    @mock.patch(f"{MODULE}.pick_targets")
    def test_duration_shorter_than_one_primary_scan(self, mock_pick_targets):
        """
        If the duration is shorter than a single primary dwell, no scans
        should be generated.
        """
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=2),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        assert len(scans) == 0

    @mock.patch(f"{MODULE}.pick_targets")
    def test_no_targets_visible(self, mock_pick_targets):
        """
        When pick_targets returns no primary, the SBD should be returned
        with an empty scan sequence.
        """
        mock_pick_targets.return_value = Targets(primary=None, secondary=None)

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=30),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        assert len(scans) == 0
        assert len(sbd.targets) == 0

    @mock.patch(f"{MODULE}.pick_targets")
    def test_primary_only_no_secondaries(self, mock_pick_targets):
        """
        When only a primary target is visible (no secondaries), only primary
        scans should be produced.
        """
        mock_pick_targets.return_value = create_mock_targets(secondary_names=[])

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=15),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=timedelta(minutes=5),
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        # 15 min / 5 min dwell = 3 primary-only scans
        assert len(scans) == 3
        # All targets should be the primary (CalibratorA)
        target_names = {
            next(t.name for t in sbd.targets if t.target_id == s.target_ref) for s in scans
        }
        assert target_names == {"CalibratorA"}

    @mock.patch(f"{MODULE}.pick_targets")
    def test_secondary_dwell_none_skips_secondaries(self, mock_pick_targets):
        """
        When secondary_dwell is None, secondary targets should be skipped.
        """
        mock_pick_targets.return_value = create_mock_targets()

        sbd = generate_cal_sweep_sbd(
            obs_start=TEST_OBS_START,
            duration=timedelta(minutes=15),
            primary_dwell=timedelta(minutes=5),
            secondary_dwell=None,
        )

        scans = sbd.mccs_allocation.subarray_beams[0].scan_sequence
        # With no secondary dwell, only primaries: 15/5 = 3 scans
        assert len(scans) == 3
