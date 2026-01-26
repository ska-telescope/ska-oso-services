from unittest import mock

from ska_oso_pdm import SBDefinition

from ska_oso_services.odt.service.sbd_generator import generate_sbds
from tests.unit.odt.api.test_sdp import patch_env_var  # pylint: disable=unused-import
from tests.unit.util import TestDataFactory, load_string_from_file


@mock.patch("ska_oso_services.odt.service.sbd_generator.randint")
def test_sbds_generated_from_observing_block_with_two_mid_observation_groups(
    mock_randint,
):
    mock_randint.return_value = 12345
    project = TestDataFactory.project_with_two_mid_observation_groups()
    ob = project.obs_blocks[0]
    data = load_string_from_file("expected_mid_sbd.json")
    expected_sbd = SBDefinition.model_validate_json(data)
    expected_sbd.ob_ref = ob.obs_block_id

    sbds = generate_sbds(ob)

    assert len(sbds) == 2
    assert sbds[0] == expected_sbd


@mock.patch("ska_oso_services.odt.service.sbd_generator.randint")
def test_sbds_generated_from_observing_block_with_two_low_targets(mock_randint):
    # The different types can all reuse the same id, but the second scan
    # should have a different one so the test checks the linking is done correctly
    mock_randint.side_effect = [12345, 12345, 67890, 12345, 56789, 28364, 39474, 74039]
    project = TestDataFactory.project_with_two_low_targets()
    ob = project.obs_blocks[0]
    data = load_string_from_file("expected_low_sbd.json")
    expected_sbd = SBDefinition.model_validate_json(data)
    expected_sbd.ob_ref = ob.obs_block_id

    sbds = generate_sbds(ob)

    assert len(sbds) == 1
    assert sbds[0] == expected_sbd


@mock.patch("ska_oso_services.odt.service.sbd_generator.randint")
def test_sbds_generated_from_observing_block_without_calibration_strategy(mock_randint):
    mock_randint.return_value = 12345
    project = TestDataFactory.project_with_two_low_targets()
    ob = project.obs_blocks[0]

    ob.science_programmes[0].calibration_strategies = []

    sbds = generate_sbds(ob)

    assert len(sbds) == 1
    assert sbds[0].description is None
