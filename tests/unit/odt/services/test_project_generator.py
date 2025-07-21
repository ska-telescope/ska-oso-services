from ska_oso_services.odt.service.project_generator import generate_project
from tests.unit.util import TestDataFactory


def test_project_from_proposal_without_groups():
    """
    The input Proposal has two observation sets that are not linked via groups.
    The first has two targets and the second has one target, and they both use
    the same SDP section.

    This test then checks that the Project is created with two Observing Blocks
    with the correct data from the Proposal
    """

    proposal = TestDataFactory.complete_proposal()
    proposal.info.observation_sets[0].group_id = None
    proposal.info.observation_sets[1].group_id = None

    project = generate_project(proposal)
    assert proposal.prsl_id == project.prsl_ref
    assert len(project.obs_blocks) == 2

    # Check the first observing block contents
    first_obs_block = project.obs_blocks[0]
    assert first_obs_block.obs_block_id == "obs-block-00001"
    assert len(first_obs_block.science_programmes) == 1
    first_ob_science_programme = first_obs_block.science_programmes[0]

    assert len(first_ob_science_programme.observation_sets) == 1
    assert (
        proposal.info.observation_sets[0]
        == first_ob_science_programme.observation_sets[0]
    )

    # There are two targets linked to the first observation_set, via the result_details
    assert len(first_ob_science_programme.result_details) == 2
    assert len(first_ob_science_programme.targets) == 2

    assert (
        proposal.info.data_product_sdps == first_ob_science_programme.data_product_sdps
    )

    # Check the second observing block contents
    second_obs_block = project.obs_blocks[1]
    assert len(second_obs_block.science_programmes) == 1
    second_ob_science_programme = second_obs_block.science_programmes[0]

    assert len(second_ob_science_programme.observation_sets) == 1
    assert (
        proposal.info.observation_sets[1]
        == second_ob_science_programme.observation_sets[0]
    )

    # There is one target linked to the second observation_set, via the result_details
    assert len(second_ob_science_programme.result_details) == 1
    assert len(second_ob_science_programme.targets) == 1

    assert (
        proposal.info.data_product_sdps == first_ob_science_programme.data_product_sdps
    )


def test_project_from_proposal_with_groups():
    """
    The input Proposal has two observation sets that are linked via the same group.
    The first has two targets and the second has one target, and they both use
    the same SDP section.

    This test then checks that the Project is created with a single Observing Block
    with two science programmes, each with the correct data from the Proposal
    """

    proposal = TestDataFactory.complete_proposal()
    proposal.info.observation_sets[0].group_id = "1"
    proposal.info.observation_sets[1].group_id = "1"

    project = generate_project(proposal)
    assert proposal.prsl_id == project.prsl_ref
    assert len(project.obs_blocks) == 1

    # Check the observing block has two science programmes
    first_obs_block = project.obs_blocks[0]
    assert len(first_obs_block.science_programmes) == 2

    # Check the first science programme
    ob_first_science_programme = first_obs_block.science_programmes[0]

    assert len(ob_first_science_programme.observation_sets) == 1
    assert (
        proposal.info.observation_sets[0]
        == ob_first_science_programme.observation_sets[0]
    )

    # There are two targets linked to the first observation_set, via the result_details
    assert len(ob_first_science_programme.result_details) == 2
    assert len(ob_first_science_programme.targets) == 2

    assert (
        proposal.info.data_product_sdps == ob_first_science_programme.data_product_sdps
    )

    # Check the second science programme
    ob_second_science_programme = first_obs_block.science_programmes[1]

    assert len(ob_second_science_programme.observation_sets) == 1
    assert (
        proposal.info.observation_sets[1]
        == ob_second_science_programme.observation_sets[0]
    )

    # There is one target linked to the second observation_set, via the result_details
    assert len(ob_second_science_programme.result_details) == 1
    assert len(ob_second_science_programme.targets) == 1

    # There are no links for the second observation_set in the test data
    assert ob_second_science_programme.data_product_sdps == []
