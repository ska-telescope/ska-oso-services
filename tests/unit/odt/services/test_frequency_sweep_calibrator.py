from datetime import timedelta
from unittest import mock

from ska_oso_pdm import ICRSCoordinates, Target

from ska_oso_services.odt.service.frequency_sweep_calibrator import generate_frequency_sweep
from tests.unit.util import assert_json_is_equal, load_string_from_file

MODULE = "ska_oso_services.odt.service.frequency_sweep_calibrator"


def create_target() -> Target:
    return Target(
        target_id="target-00001",
        name="TestTarget",
        reference_coordinate=ICRSCoordinates(ra_str="12:30:00", dec_str="-30:00:00"),
    )


class TestGenerateFrequencySweep:
    @mock.patch(f"{MODULE}.generate_csp_configuration_id")
    @mock.patch(f"{MODULE}.scan_definition_id")
    def test_generates_expected_sbd_against_full_fixture(
        self, mock_scan_definition_id, mock_generate_csp_configuration_id
    ):
        mock_generate_csp_configuration_id.side_effect = [
            "csp-config-00001",
            "csp-config-00002",
            "csp-config-00003",
            "csp-config-00004",
        ]
        mock_scan_definition_id.side_effect = [
            "scan-00001",
            "scan-00002",
            "scan-00003",
            "scan-00004",
        ]

        sbd = generate_frequency_sweep(
            target=create_target(),
            target_dwell=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_end=448,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345, 350, 352, 431],
        )

        sbd.metadata = None
        expected_json = load_string_from_file("expected_freq_sweep_sbd.json")
        assert_json_is_equal(
            sbd.model_dump_json(),
            expected_json,
            exclude_paths=["root['mccs_allocation']['mccs_allocation_id']"],
        )

    @mock.patch(f"{MODULE}.generate_csp_configuration_id")
    @mock.patch(f"{MODULE}.scan_definition_id")
    def test_generates_expected_number_of_scans_for_even_span(
        self, mock_scan_definition_id, mock_generate_csp_configuration_id
    ):
        mock_generate_csp_configuration_id.side_effect = [
            "csp-config-00001",
            "csp-config-00002",
            "csp-config-00003",
            "csp-config-00004",
        ]
        mock_scan_definition_id.side_effect = [
            "scan-00001",
            "scan-00002",
            "scan-00003",
            "scan-00004",
        ]

        sbd = generate_frequency_sweep(
            target=create_target(),
            target_dwell=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_end=448,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345],
        )

        assert len(sbd.targets) == 1
        assert len(sbd.csp_configurations) == 4
        assert len(sbd.mccs_allocation.subarray_beams[0].scan_sequence) == 4

    @mock.patch(f"{MODULE}.generate_csp_configuration_id")
    @mock.patch(f"{MODULE}.scan_definition_id")
    def test_generates_expected_number_of_scans_for_uneven_span(
        self, mock_scan_definition_id, mock_generate_csp_configuration_id
    ):
        mock_generate_csp_configuration_id.side_effect = [
            "csp-config-00001",
            "csp-config-00002",
            "csp-config-00003",
        ]
        mock_scan_definition_id.side_effect = ["scan-00001", "scan-00002", "scan-00003"]

        sbd = generate_frequency_sweep(
            target=create_target(),
            target_dwell=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_end=350,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345],
        )

        assert len(sbd.csp_configurations) == 3
        assert len(sbd.mccs_allocation.subarray_beams[0].scan_sequence) == 3

    def test_sets_pst_parts_when_mode_is_pst(self):
        target = create_target()
        sbd = generate_frequency_sweep(
            target=target,
            target_dwell=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_end=160,
            coarse_channel_bandwidth=96,
            pst_mode=True,
            stations=[345],
        )

        assert all(csp.lowcbf.do_pst for csp in sbd.csp_configurations)
        assert len(sbd.targets[0].tied_array_beams.pst_beams) == 1
        assert (
            sbd.targets[0].tied_array_beams.pst_beams[0].beam_coordinate
            == target.reference_coordinate
        )

    def test_scan_sequence_references_single_target(self):
        target = create_target()
        sbd = generate_frequency_sweep(
            target=target,
            target_dwell=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_end=256,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345],
        )

        for scan in sbd.mccs_allocation.subarray_beams[0].scan_sequence:
            assert scan.target_ref == target.target_id
