"""
Component level tests for the /oda/prsls paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

import json
from http import HTTPStatus

from requests import Session
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token
from ska_ser_skuid import EntityType, mint_skuid

from ..unit.util import TestDataFactory
from . import PHT_URL
from .conftest import AUDIENCE

PANELS_API_URL = f"{PHT_URL}/panels"


def test_get_osd_data_fail(authrequests):
    cycle = 9999
    response = authrequests.get(f"{PHT_URL}/prsls/osd/{cycle}")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_get_osd_data_success(authrequests):
    cycle = 1
    response = authrequests.get(f"{PHT_URL}/prsls/osd/{cycle}")

    res = response.json()
    assert res["observatory_policy"]["cycle_number"] == 1
    assert res["observatory_policy"]["cycle_information"]["cycle_id"] == "TEST_SKAO_2027_1"


def test_get_osd_cycles_success(authrequests):
    response = authrequests.get(f"{PHT_URL}/prsls/osd/cycles")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0  # ensures OSD is reachable and cycles are returned


def test_create_and_get_proposal(authrequests):
    """
    Integration test for the POST /prsls/create endpoint
    and GET /prsls/{prsl_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]
    assert isinstance(prsl_id, str), f"Expected string, got {type(prsl_id)}: {prsl_id}"

    # GET created proposal
    get_response = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_response.status_code == HTTPStatus.OK, get_response.content
    actual_payload = get_response.json()

    # Prepare expected payload from input
    expected_payload = json.loads(TestDataFactory.proposal().model_dump_json())

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("prsl_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)
        if "investigators" in obj["proposal_info"]:
            obj["proposal_info"].pop("investigators", None)

    assert actual_payload == expected_payload


def test_proposal_create_then_put(authrequests):
    """
    POST /prsls/create with a unique prsl_id, then PUT /prsls/{identifier}
    and verify metadata.version increments.
    """

    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # Get the created proposal
    get_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v1.status_code == HTTPStatus.OK, get_v1.content
    v1 = get_v1.json()["metadata"]["version"]

    # Update title and PUT back
    updated_entity = get_v1.json()
    updated_entity["title"] = f"{updated_entity.get('title', 'Untitled')} (updated title)"
    put_resp = authrequests.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=json.dumps(updated_entity),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.OK, put_resp.content

    # Verify version increment
    get_v2 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v2.status_code == HTTPStatus.OK, get_v2.content
    assert get_v2.json()["metadata"]["version"] == v1 + 1


def test_proposal_create_then_put_submit(authrequests):
    """
    POST /prsls/create with a unique prsl_id
    then PUT /prsls/{identifier} using complete submit proposal
    and verify metadata.version increments.
    """
    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # Get the created proposal
    get_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v1.status_code == HTTPStatus.OK, get_v1.content
    v1 = get_v1.json()["metadata"]["version"]

    # Use a completed proposal with submitted status and PUT back
    updated_complete_submit_proposal = TestDataFactory.complete_proposal(prsl_id=prsl_id)

    put_resp = authrequests.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=updated_complete_submit_proposal.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.OK, put_resp.content

    # Verify version increment
    get_v2 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v2.status_code == HTTPStatus.OK, get_v2.content
    assert get_v2.json()["metadata"]["version"] == v1 + 1


def test_proposal_update_forbidden_for_non_member(authrequests):
    """
    A user with no proposal-specific group and no PHT admin group must get 403
    when trying to PUT a proposal they didn't create and have no access to.
    """
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # A token with no groups at all — cannot view or edit any specific proposal
    non_member_session = Session()
    non_member_session.headers["Authorization"] = "Bearer " + mint_test_token(
        audience=AUDIENCE,
        roles=[Role.ANY],
        scopes=["pht:read", "pht:readwrite"],
        groups=[],
    )

    put_resp = non_member_session.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=TestDataFactory.proposal(prsl_id=prsl_id).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.FORBIDDEN


def test_proposal_submit_forbidden_for_non_member(authrequests):
    """
    A non-member user must not be able to submit a proposal they have no access to.
    """
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    non_member_session = Session()
    non_member_session.headers["Authorization"] = "Bearer " + mint_test_token(
        audience=AUDIENCE,
        roles=[Role.ANY],
        scopes=["pht:read", "pht:readwrite"],
        groups=[],
    )

    put_resp = non_member_session.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=TestDataFactory.complete_proposal(prsl_id=prsl_id).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.FORBIDDEN


def test_get_proposals_batch(authrequests):
    """
    Integration test:
    - Create multiple proposals with unique IDs
    - Use POST /batch to retrieve them
    - Ensure all created proposals are returned
    """

    created_ids = []

    # Create 3 proposals with unique prsl_ids
    for _ in range(3):
        proposal = TestDataFactory.proposal()
        proposal_json = proposal.model_dump_json()

        response = authrequests.post(
            f"{PHT_URL}/prsls/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids.append(response.json()["prsl_id"])

    # Use POST /batch to retrieve them
    batch_response = authrequests.post(
        f"{PHT_URL}/prsls/batch",
        json={"prsl_ids": created_ids},
    )

    assert batch_response.status_code == HTTPStatus.OK, batch_response.content

    proposals = batch_response.json()
    assert isinstance(proposals, list), "Expected a list of proposals"
    assert len(proposals) == len(created_ids), (
        f"Expected {len(created_ids)} proposals, got {len(proposals)}"
    )

    returned_ids = {p["prsl_id"] for p in proposals}
    for prsl_id in created_ids:
        assert prsl_id in returned_ids, f"Missing proposal {prsl_id} in POST /batch"


def test_get_reviews_for_panel_with_wrong_id(authrequests):
    prsl_id = mint_skuid(EntityType.PRP)
    response = authrequests.get(f"{PHT_URL}/prsls/reviews/{prsl_id}")
    assert response.status_code == HTTPStatus.OK
    res = response.json()
    assert [] == res


def test_get_reviews_for_panel_with_valid_id(authrequests):
    proposal = TestDataFactory.complete_proposal()
    response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    prsl_id = response.json()["prsl_id"]
    assert response.status_code == HTTPStatus.OK

    panel_id = mint_skuid(EntityType.PNL)
    panel = TestDataFactory.panel_basic(panel_id=panel_id)
    response = authrequests.post(
        f"{PANELS_API_URL}/create",
        data=panel.model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK, response.content
    review = [TestDataFactory.reviews(prsl_id=prsl_id, panel_id=panel_id)]
    response = authrequests.post(
        f"{PHT_URL}/reviews/create",
        data=review[0].json(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK

    response = authrequests.get(f"{PHT_URL}/prsls/reviews/{prsl_id}")
    assert response.status_code == HTTPStatus.OK
    res = response.json()
    del res[0]["metadata"]
    expected = [obj.model_dump(mode="json", exclude={"metadata"}) for obj in review]
    assert expected == res


def test_get_proposals_by_status(authrequests):
    """
    - Create proposals with various statuses (e.g. 'pending', 'rejected', 'submitted')
    - Fetch proposals using GET /prsls/status/{status}
    - Check that only proposals with the requested status are returned
    """

    status_to_test = "submitted"
    created_ids_with_target_status = []
    created_ids_with_other_status = []

    # Create proposals with the target status to test
    for _ in range(3):
        proposal = TestDataFactory.complete_proposal(status=status_to_test)
        proposal_json = proposal.model_dump_json()

        response = authrequests.post(
            f"{PHT_URL}/prsls/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids_with_target_status.append(proposal.prsl_id)

    # Create proposals with different statuses additionally
    for status in ["draft", "rejected"]:
        prsl_id = mint_skuid(EntityType.PRP)
        proposal = TestDataFactory.complete_proposal(prsl_id=prsl_id, status=status)
        proposal_json = proposal.model_dump_json()

        response = authrequests.post(
            f"{PHT_URL}/prsls/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids_with_other_status.append(prsl_id)

    # Get proposals by 'draft' status
    status_response = authrequests.get(f"{PHT_URL}/prsls/reviewable")
    assert status_response.status_code == HTTPStatus.OK, status_response.content

    proposals = status_response.json()
    assert isinstance(proposals, list)

    returned_ids = {p["prsl_id"] for p in proposals}

    # All with 'draft' should be returned
    for prsl_id in created_ids_with_target_status:
        assert prsl_id in returned_ids, f"Missing {prsl_id} from GET /status/{status_to_test}"

    # Other statuses should not be returned
    for prsl_id in created_ids_with_other_status:
        assert prsl_id not in returned_ids, (
            f"Unexpected proposal {prsl_id} in GET /status/{status_to_test}"
        )
