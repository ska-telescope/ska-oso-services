"""
Component level tests for the commissioning SBDefinition generation endpoints.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster.
"""

# pylint: disable=missing-timeout
from http import HTTPStatus

from ska_oso_pdm import Project

from ..unit.util import TestDataFactory
from . import ODT_URL


class TestCalibratorSweepSBDefinitionGeneration:
    CAL_SWEEP_INPUT = {
        "obs_start": "2026-06-15T10:00:00",
        "duration_min": 30,
        "primary_dwell_min": 5,
        "secondary_dwell_min": 5,
        "interleave_primary": False,
        "coarse_channel_start": 206,
        "coarse_channel_bandwidth": 96,
        "mode": "PST",
    }

    def test_cal_sweep_sbd_generated_and_persisted(self, authrequests):
        """
        A valid request should generate, persist and link a calibrator sweep SBDefinition.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateCalibratorSweepSBDefinition",
            json=self.CAL_SWEEP_INPUT,
        )

        assert generate_response.status_code == HTTPStatus.OK, generate_response.text
        updated_project = Project.model_validate_json(generate_response.text)

        assert len(updated_project.obs_blocks[0].sbd_ids) >= 1

        sbd_id = updated_project.obs_blocks[0].sbd_ids[-1]
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK


class TestFrequencySweepSBDefinitionGeneration:
    def test_frequency_sweep_sbd_generated_with_ra_dec(self, authrequests):
        """
        A valid request with explicit RA/Dec should generate and persist a
        frequency sweep SBDefinition.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        frequency_sweep_input = {
            "target_name": None,
            "ra_str": "12:30:00",
            "dec_str": "-30:00:00",
            "target_dwell_min": 5,
            "coarse_channel_start": 64,
            "coarse_channel_end": 448,
            "coarse_channel_bandwidth": 96,
            "mode": "VIS",
        }
        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateFrequencySweepSBDefinition",
            json=frequency_sweep_input,
        )

        assert generate_response.status_code == HTTPStatus.OK, generate_response.text
        updated_project = Project.model_validate_json(generate_response.text)

        assert len(updated_project.obs_blocks[0].sbd_ids) >= 1

        sbd_id = updated_project.obs_blocks[0].sbd_ids[-1]
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK


class TestBasicCommissioningSBDefinitionGeneration:
    def test_basic_commissioning_sbd_generated_with_ra_dec(self, authrequests):
        """
        A valid request with explicit RA/Dec should generate and persist a
        basic commissioning SBDefinition.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        basic_commissioning_input = {
            "name": "Basic Commissioning",
            "duration_min": 5,
            "target_name": None,
            "ra_str": "12:30:00",
            "dec_str": "-30:00:00",
            "coarse_channel_start": 64,
            "coarse_channel_bandwidth": 96,
            "mode": "VIS",
        }
        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateBasicCommissioningSBDefinition",
            json=basic_commissioning_input,
        )

        assert generate_response.status_code == HTTPStatus.OK, generate_response.text
        updated_project = Project.model_validate_json(generate_response.text)

        assert len(updated_project.obs_blocks[0].sbd_ids) >= 1

        sbd_id = updated_project.obs_blocks[0].sbd_ids[-1]
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK

    def test_basic_commissioning_sbd_generated_with_target_name(self, authrequests):
        """
        A valid request using a catalogue target name should resolve coordinates
        and generate a basic commissioning SBDefinition.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        basic_commissioning_input = {
            "name": "Centaurus A Commissioning",
            "duration_min": 5,
            "target_name": "Centaurus A",
            "ra_str": None,
            "dec_str": None,
            "coarse_channel_start": 64,
            "coarse_channel_bandwidth": 96,
            "mode": "VIS",
        }
        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateBasicCommissioningSBDefinition",
            json=basic_commissioning_input,
        )

        assert generate_response.status_code == HTTPStatus.OK, generate_response.text
        updated_project = Project.model_validate_json(generate_response.text)

        assert len(updated_project.obs_blocks[0].sbd_ids) >= 1

        sbd_id = updated_project.obs_blocks[0].sbd_ids[-1]
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK

    def test_basic_commissioning_target_name_47_tuc_returns_validation_error(self, authrequests):
        """
        Target name '47 Tuc' should fail commissioning SBD validation and return 400.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        basic_commissioning_input = {
            "name": "47 Tuc Commissioning",
            "duration_min": 5,
            "target_name": "47 Tuc",
            "ra_str": None,
            "dec_str": None,
            "coarse_channel_start": 64,
            "coarse_channel_bandwidth": 96,
            "mode": "VIS",
        }
        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateBasicCommissioningSBDefinition",
            json=basic_commissioning_input,
        )

        assert generate_response.status_code == HTTPStatus.BAD_REQUEST, generate_response.text
        assert (
            generate_response.json()["detail"] == "SBDefinition validation failed with issues "
            "['$.targets.0: Maximum elevation (44.74 degrees) "
            "is less than the limit (45.0 degrees)']"
        )


class TestGSMSurveySBDefinitionGeneration:
    def test_gsm_survey_sbds_generated_and_persisted(self, authrequests):
        """
        A valid request should generate and persist GSM survey SBDefinitions.
        The max_rows parameter limits pointings for a lightweight test.
        """
        project = TestDataFactory.project_with_two_low_targets(prj_id=None, prsl_ref=None)
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert post_response.status_code == HTTPStatus.OK, post_response.text
        prj_id = post_response.json()["prj_id"]
        obs_block_id = post_response.json()["obs_blocks"][0]["obs_block_id"]

        survey_input = {
            "pointings_file_uri": "hex_relax_beams.sweet_as.csv",
            "centre_frequency_mhz": 155.47,
            "scan_duration_min": 5.0,
            "num_subarray_beams": 2,
            "num_scans": 3,
            "max_rows": 6,
        }
        generate_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/generateGSMSurveySBDefinitions",
            json=survey_input,
        )

        assert generate_response.status_code == HTTPStatus.OK, generate_response.text
        updated_project = Project.model_validate_json(generate_response.text)

        # 6 targets / (2 beams * 3 scans) = 1 SBD
        assert len(updated_project.obs_blocks[0].sbd_ids) == 1

        sbd_id = updated_project.obs_blocks[0].sbd_ids[0]
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK
