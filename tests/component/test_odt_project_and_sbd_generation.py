from http import HTTPStatus

from ska_oso_pdm import Project

from tests.unit.util import TestDataFactory

from . import ODT_URL, PHT_URL


def test_project_generated_from_proposal(authrequests):
    # First need to add a proposal to generate from
    proposal = TestDataFactory.complete_proposal()
    proposal.prsl_id = None
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    # Generate the Project
    generate_response = authrequests.post(f"{ODT_URL}/prsls/{prsl_id}/generateProject")

    assert generate_response.status_code == HTTPStatus.OK, generate_response.text
    assert prsl_id == generate_response.json()["prsl_ref"]

    # Check the Project exists in the ODA
    prj_id = generate_response.json()["prj_id"]
    get_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")

    assert get_response.status_code == HTTPStatus.OK


def test_sbds_generated_from_project(authrequests):
    # First need to add a Project to generate from
    project = TestDataFactory.project_with_two_mid_observation_groups(prj_id=None)
    post_response = authrequests.post(
        f"{ODT_URL}/prjs",
        data=project.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prj_id = post_response.json()["prj_id"]

    # Generate the SBDefinitions
    generate_response = authrequests.post(f"{ODT_URL}/prjs/{prj_id}/generateSBDefinitions")

    assert generate_response.status_code == HTTPStatus.OK, generate_response.text
    project = Project.model_validate_json(generate_response.text)

    # Check that two SBDefinitions are created from the input data
    assert len(project.obs_blocks[0].sbd_ids) == 2

    # Check the SBDefinitions exists in the ODA
    for sbd_id in project.obs_blocks[0].sbd_ids:
        get_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_response.status_code == HTTPStatus.OK


def test_sbds_generated_from_project_obs_block(authrequests):
    # First need to add a Project to generate from
    project = TestDataFactory.project_with_two_low_targets(prj_id=None)
    post_response = authrequests.post(
        f"{ODT_URL}/prjs",
        data=project.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prj_id = post_response.json()["prj_id"]

    # Generate the SBDefinitions
    generate_response = authrequests.post(
        f"{ODT_URL}/prjs" f"/{prj_id}/{project.obs_blocks[0].obs_block_id}/generateSBDefinitions"
    )

    assert generate_response.status_code == HTTPStatus.OK, generate_response.text
    project = Project.model_validate_json(generate_response.text)

    # Check that one SBDefinitions is created from the input data (one observation sets)
    assert len(project.obs_blocks[0].sbd_ids) == 1

    # Check the SBDefinitions exists in the ODA
    get_response = authrequests.get(f"{ODT_URL}/sbds/{project.obs_blocks[0].sbd_ids[0]}")
    assert get_response.status_code == HTTPStatus.OK
