from ska_oso_pdm import SBDefinition

from ska_oso_services.odt.service.sbd_generator import generate_sbds
from tests.unit.util import TestDataFactory, load_string_from_file


def test_sbds_generated_from_observing_block_with_two_mid_observation_groups():
    project = TestDataFactory.project_with_two_mid_observation_groups()
    ob = project.obs_blocks[0]
    data = load_string_from_file("expected_mid_sbd.json")
    expected_sbd = SBDefinition.model_validate_json(data)

    sbds = generate_sbds(ob)

    assert len(sbds) == 2
    assert sbds[0] == expected_sbd


def test_sbds_generated_from_observing_block_with_two_low_targets():
    project = TestDataFactory.project_with_two_low_targets()
    ob = project.obs_blocks[0]
    data = load_string_from_file("expected_low_sbd.json")
    expected_sbd = SBDefinition.model_validate_json(data)

    sbds = generate_sbds(ob)

    assert len(sbds) == 1
    assert sbds[0] == expected_sbd
