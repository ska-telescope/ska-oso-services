# pylint: disable=no-member

from datetime import timedelta
from unittest import mock

from ska_oso_pdm import ICRSCoordinates, Target

from ska_oso_services.odt.service.basic_commissioning_sbd_generator import (
    generate_basic_commissioning_sbd,
)

MODULE = "ska_oso_services.odt.service.basic_commissioning_sbd_generator"


def create_target() -> Target:
    return Target(
        target_id="target-00001",
        name="TestTarget",
        reference_coordinate=ICRSCoordinates(ra_str="12:30:00", dec_str="-30:00:00"),
    )


class TestGenerateBasicCommissioningSBD:
    @mock.patch(f"{MODULE}.csp_configuration_id")
    @mock.patch(f"{MODULE}.scan_definition_id")
    def test_generates_single_scan_and_csp_configuration(
        self, mock_scan_definition_id, mock_csp_configuration_id
    ):
        mock_csp_configuration_id.return_value = "csp-config-00001"
        mock_scan_definition_id.return_value = "scan-00001"

        sbd = generate_basic_commissioning_sbd(
            name="Basic Commissioning",
            target=create_target(),
            duration=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345, 350, 352, 431],
        )

        assert len(sbd.targets) == 1
        assert len(sbd.csp_configurations) == 1
        assert len(sbd.mccs_allocation.subarray_beams[0].scan_sequence) == 1

    def test_scan_references_the_target_and_csp_configuration(self):
        target = create_target()
        sbd = generate_basic_commissioning_sbd(
            name="Basic Commissioning",
            target=target,
            duration=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345],
        )

        scan = sbd.mccs_allocation.subarray_beams[0].scan_sequence[0]
        assert scan.target_ref == target.target_id
        assert scan.csp_configuration_ref == sbd.csp_configurations[0].config_id
        assert scan.scan_duration_ms == timedelta(minutes=5)

    def test_does_not_set_pst_parts_when_mode_is_vis(self):
        target = create_target()
        sbd = generate_basic_commissioning_sbd(
            name="Basic Commissioning",
            target=target,
            duration=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_bandwidth=96,
            pst_mode=False,
            stations=[345],
        )

        assert all(not csp.lowcbf.do_pst for csp in sbd.csp_configurations)
        assert sbd.targets[0].tied_array_beams.pst_beams == []

    def test_sets_pst_parts_when_mode_is_pst(self):
        target = create_target()
        stations = [345, 350, 352]
        sbd = generate_basic_commissioning_sbd(
            name="Basic Commissioning",
            target=target,
            duration=timedelta(minutes=5),
            coarse_channel_start=64,
            coarse_channel_bandwidth=96,
            pst_mode=True,
            stations=stations,
        )

        assert all(csp.lowcbf.do_pst for csp in sbd.csp_configurations)
        pst_beams = sbd.targets[0].tied_array_beams.pst_beams
        assert len(pst_beams) == 1
        assert pst_beams[0].beam_coordinate == target.reference_coordinate
        assert pst_beams[0].stn_weights == [1.0] * len(stations)
