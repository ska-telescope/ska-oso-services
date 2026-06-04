from datetime import timedelta
from unittest import mock

# pylint: disable=no-member
import astropy.units as u
from astropy.units import Quantity
from ska_oso_pdm import ICRSCoordinates, Target

from ska_oso_services.odt.service.gsm_survey_sbd_generator import generate_gsm_survey_sbds
from tests.unit.util import assert_json_is_equal, load_string_from_file

MODULE = "ska_oso_services.odt.service.gsm_survey_sbd_generator"


def _make_targets(count: int) -> list[Target]:
    return [
        Target(
            target_id=f"target-{i:04d}",
            name=f"Target {i}",
            reference_coordinate=ICRSCoordinates(
                ra_str=f"{i % 24}:00:00",
                dec_str="-30:00:00",
            ),
        )
        for i in range(count)
    ]


class TestGenerateGSMSBDs:

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_correct_number_of_sbds(self, _mock_id):
        """
        With 12 targets, 2 subarray beams, and 3 scans per beam,
        each SBD uses 6 targets, so 2 SBDs should be produced.
        """

        targets = _make_targets(12)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=2,
            num_scans=3,
            num_calibrator_beams=0,
        )

        assert len(sbds) == 2

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_first_sbd_json(self, _mock_id):
        """Test the first SBDefinition is of the correct form with correct defaults"""

        targets = _make_targets(6)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=2,
            num_scans=3,
            num_calibrator_beams=1,
        )

        assert len(sbds) == 1

        expected_json = load_string_from_file("expected_gsm_sbd.json")
        assert_json_is_equal(
            sbds[0].model_dump_json(),
            expected_json,
        )


class TestRemainderHandling:
    """Tests for when targets don't evenly divide into SBDs."""

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_remainder_creates_extra_sbd(self, _mock_id):
        """
        29 targets with 4 beams * 3 scans = 12 per SBD.
        2 full SBDs (24 targets) + 1 remainder SBD (5 targets).
        """

        targets = _make_targets(29)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=4,
            num_scans=3,
            num_calibrator_beams=0,
        )

        assert len(sbds) == 3
        # First two SBDs are full
        assert len(sbds[0].targets) == 12
        assert len(sbds[1].targets) == 12
        # Remainder SBD has the leftover 5 targets
        assert len(sbds[2].targets) == 5

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_remainder_beams_have_equal_scans(self, _mock_id):
        """
        5 remaining targets with max 4 beams: best layout is 5 beams x 1 scan.
        All subarray beams must have the same number of scans.
        """

        targets = _make_targets(29)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=4,
            num_scans=3,
            num_calibrator_beams=0,
        )

        remainder_sbd = sbds[2]
        beams = remainder_sbd.mccs_allocation.subarray_beams
        scan_counts = [len(b.scan_sequence) for b in beams]
        # All beams must have the same number of scans
        assert len(set(scan_counts)) == 1

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_remainder_uses_max_beams_when_divisible(self, _mock_id):
        """
        8 remaining targets with max 4 beams: 4 beams x 2 scans.
        """

        # 20 targets = 1 full SBD (4*3=12) + 8 remainder
        targets = _make_targets(20)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=4,
            num_scans=3,
            num_calibrator_beams=0,
        )

        assert len(sbds) == 2
        remainder_sbd = sbds[1]
        beams = remainder_sbd.mccs_allocation.subarray_beams
        assert len(beams) == 4
        for beam in beams:
            assert len(beam.scan_sequence) == 2

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_no_remainder_no_extra_sbd(self, _mock_id):
        """
        When targets divide evenly, no extra SBD should be created.
        """

        targets = _make_targets(12)
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=2,
            num_scans=3,
            num_calibrator_beams=0,
        )

        assert len(sbds) == 2

    @mock.patch(f"{MODULE}._sbd_internal_id", side_effect=lambda cls: f"{cls.__name__}-001")
    def test_single_remainder_target(self, _mock_id):
        """
        1 remaining target should produce 1 beam with 1 scan.
        """

        targets = _make_targets(7)  # 6 full + 1 remainder
        sbds = generate_gsm_survey_sbds(
            input_targets=targets,
            centre_frequency=Quantity(155.47, u.MHz),
            scan_duration=timedelta(minutes=5),
            num_subarray_beams=2,
            num_scans=3,
            num_calibrator_beams=0,
        )

        assert len(sbds) == 2
        remainder_sbd = sbds[1]
        beams = remainder_sbd.mccs_allocation.subarray_beams
        assert len(beams) == 1
        assert len(beams[0].scan_sequence) == 1
