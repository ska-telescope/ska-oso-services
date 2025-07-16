from http import HTTPStatus

import requests

from tests.unit.util import TestDataFactory

from . import ODT_URL, PHT_URL


def test_project_generated_from_proposal(authrequests):
    # First need to add a proposal to generate from
    proposal = TestDataFactory.complete_proposal()
    proposal.prsl_id = None
    post_response = requests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()

    # Generate the Project
    generate_response = authrequests.post(f"{ODT_URL}/prsls/{prsl_id}/generateProject")

    assert generate_response.status_code == HTTPStatus.OK, generate_response.text
    assert prsl_id == generate_response.json()["prsl_ref"]

    # Check the Project exists in the ODA
    prj_id = generate_response.json()["prj_id"]
    get_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")

    assert get_response.status_code == HTTPStatus.OK
