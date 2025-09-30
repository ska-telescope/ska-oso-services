"""
Component level tests for the /oda/prsls paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

import json
import uuid
from http import HTTPStatus

from ska_aaa_authhelpers.test_helpers.constants import TEST_USER

from ..unit.util import VALID_COMPLETE_PROPOSAL, VALID_NEW_PROPOSAL, TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/panels"


def test_get_osd_data_fail(authrequests):
    cycle = 9999
    response = authrequests.get(f"{PHT_URL}/prsls/osd/{cycle}")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_get_osd_data_success(authrequests):
    cycle = 1
    response = authrequests.get(f"{PHT_URL}/prsls/osd/{cycle}")

    res = response.json()
    expected = {
        "observatory_policy": {
            "cycle_number": 1,
            "cycle_description": "Science Verification",
            "cycle_information": {
                "cycle_id": "SKAO_2027_1",
                "proposal_open": "20260327T12:00:00.000Z",
                "proposal_close": "20260512T15:00:00.000z",
            },
            "cycle_policies": {"normal_max_hours": 100.0},
            "telescope_capabilities": {"Mid": "AA2", "Low": "AA2"},
        },
        "capabilities": {
            "mid": {
                "basic_capabilities": {
                    "dish_elevation_limit_deg": 15.0,
                    "receiver_information": [
                        {
                            "rx_id": "Band_1",
                            "min_frequency_hz": 350000000.0,
                            "max_frequency_hz": 1050000000.0,
                        },
                        {
                            "rx_id": "Band_2",
                            "min_frequency_hz": 950000000.0,
                            "max_frequency_hz": 1760000000.0,
                        },
                        {
                            "rx_id": "Band_3",
                            "min_frequency_hz": 1650000000.0,
                            "max_frequency_hz": 3050000000.0,
                        },
                        {
                            "rx_id": "Band_4",
                            "min_frequency_hz": 2800000000.0,
                            "max_frequency_hz": 5180000000.0,
                        },
                        {
                            "rx_id": "Band_5a",
                            "min_frequency_hz": 4600000000.0,
                            "max_frequency_hz": 8500000000.0,
                        },
                        {
                            "rx_id": "Band_5b",
                            "min_frequency_hz": 8300000000.0,
                            "max_frequency_hz": 15400000000.0,
                        },
                    ],
                },
                "AA2": {
                    "available_receivers": ["Band_1", "Band_2", "Band_5a", "Band_5b"],
                    "number_ska_dishes": 64,
                    "number_meerkat_dishes": 4,
                    "number_meerkatplus_dishes": 0,
                    "max_baseline_km": 110.0,
                    "available_bandwidth_hz": 800000000.0,
                    "number_channels": 14880,
                    "cbf_modes": ["CORR", "PST_BF", "PSS_BF"],
                    "number_zoom_windows": 16,
                    "number_zoom_channels": 14880,
                    "number_pss_beams": 384,
                    "number_pst_beams": 6,
                    "ps_beam_bandwidth_hz": 800000000.0,
                    "number_fsps": 4,
                },
            },
            "low": {
                "basic_capabilities": {
                    "min_frequency_hz": 50000000.0,
                    "max_frequency_hz": 350000000.0,
                },
                "AA2": {
                    "number_stations": 64,
                    "number_substations": 720,
                    "number_beams": 8,
                    "max_baseline_km": 40.0,
                    "available_bandwidth_hz": 150000000.0,
                    "channel_width_hz": 5400,
                    "cbf_modes": ["vis", "pst", "pss"],
                    "number_zoom_windows": 16,
                    "number_zoom_channels": 1800,
                    "number_pss_beams": 30,
                    "number_pst_beams": 4,
                    "number_vlbi_beams": 0,
                    "ps_beam_bandwidth_hz": 118000000.0,
                    "number_fsps": 10,
                },
            },
        },
    }
    assert expected == res


def test_create_and_get_proposal(authrequests):
    """
    Integration test for the POST /prsls/create endpoint
    and GET /prsls/{prsl_id}.
    Assumes the server is running and accessible.
    """

    # POST using JSON string
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=VALID_NEW_PROPOSAL,
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
    expected_payload = json.loads(VALID_NEW_PROPOSAL)

    # Strip dynamic fields
    for obj in (actual_payload, expected_payload):
        obj.pop("prsl_id", None)
        if "metadata" in obj:
            obj.pop("metadata", None)
        if "investigators" in obj["info"]:
            obj["info"].pop("investigators", None)

    assert actual_payload == expected_payload


def test_proposal_create_then_put(authrequests):
    """
    POST /prsls/create with a unique prsl_id, then PUT /prsls/{identifier}
    and verify metadata.version increments.
    """

    # Make payload unique
    data = json.loads(VALID_NEW_PROPOSAL)
    data["prsl_id"] = f"{data.get('prsl_id', 'prsl-test')}-{uuid.uuid4().hex[:6]}"

    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=json.dumps(data),
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
    updated_entity["title"] = (
        f"{updated_entity.get('title', 'Untitled')} (updated title)"
    )
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

    # Make payload unique
    data = json.loads(VALID_NEW_PROPOSAL)
    data["prsl_id"] = f"{data.get('prsl_id', 'prsl-test')}-{uuid.uuid4().hex[:6]}"

    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # Get the created proposal
    get_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v1.status_code == HTTPStatus.OK, get_v1.content
    v1 = get_v1.json()["metadata"]["version"]

    # Use a completed proposal with submitted status and PUT back
    updated_complete_submit_proposal = json.loads(VALID_COMPLETE_PROPOSAL)
    updated_complete_submit_proposal["prsl_id"] = prsl_id

    put_resp = authrequests.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=json.dumps(updated_complete_submit_proposal),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.OK, put_resp.content

    # Verify version increment
    get_v2 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v2.status_code == HTTPStatus.OK, get_v2.content
    assert get_v2.json()["metadata"]["version"] == v1 + 1


def test_proposal_create_then_put_update_forbidden(authrequests):
    """
    POST /prsls/create with a unique prsl_id
    GET /proposal-access/{prsl_id} to get list of proposal access
    filter returned proposal access by TEST_USER
    PUT /proposal-access/{access_id} to remove(update) submit
    then PUT /prsls/{identifier} to update proposal
    verify return forbidden and version increment does not occur
    """

    # Make payload unique
    data = json.loads(VALID_NEW_PROPOSAL)
    data["prsl_id"] = f"{data.get('prsl_id', 'prsl-test')}-{uuid.uuid4().hex[:6]}"

    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # Get the created proposal
    get_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v1.status_code == HTTPStatus.OK, get_v1.content
    v1 = get_v1.json()["metadata"]["version"]

    # Get my proposal access record and remove(update) access from proposal access
    access_records = authrequests.get(f"{PHT_URL}/proposal-access/{prsl_id}")

    filtered_access = [
        obj for obj in access_records.json() if obj.get("user_id") == TEST_USER
    ]
    my_access_record = filtered_access[0]
    my_access_id = my_access_record["access_id"]

    my_access_record["permissions"] = ["view"]

    authrequests.put(
        f"{PHT_URL}/proposal-access/user/{my_access_id}",
        data=json.dumps(my_access_record),
        headers={"Content-Type": "application/json"},
    )

    # Update title and PUT back
    updated_entity = get_v1.json()
    updated_entity["title"] = (
        f"{updated_entity.get('title', 'Untitled')} (updated title)"
    )
    put_resp = authrequests.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=json.dumps(updated_entity),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.FORBIDDEN

    # Verify version increment not occured
    get_still_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_still_v1.status_code == HTTPStatus.OK, get_still_v1.content
    assert get_still_v1.json()["metadata"]["version"] == v1


def test_proposal_create_then_put_submit_forbidden(authrequests):
    """
    POST /prsls/create with a unique prsl_id
    GET /proposal-access/{prsl_id} to get list of proposal access
    filter returned proposal access by TEST_USER
    PUT /proposal-access/{access_id} to remove(update) submit/update permission
    then PUT /prsls/{identifier}
    verify return forbidden and version increment does not occur
    """

    # Make payload unique
    data = json.loads(VALID_NEW_PROPOSAL)
    data["prsl_id"] = f"{data.get('prsl_id', 'prsl-test')}-{uuid.uuid4().hex[:6]}"

    # Create proposal
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.content
    prsl_id = post_response.json()["prsl_id"]

    # Get the created proposal
    get_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_v1.status_code == HTTPStatus.OK, get_v1.content
    v1 = get_v1.json()["metadata"]["version"]

    # Get my proposal access record and remove(update) access from proposal access
    access_records = authrequests.get(f"{PHT_URL}/proposal-access/{prsl_id}")

    filtered_access = [
        obj for obj in access_records.json() if obj.get("user_id") == TEST_USER
    ]
    my_access_record = filtered_access[0]
    my_access_id = my_access_record["access_id"]

    my_access_record["permissions"] = ["view"]

    authrequests.put(
        f"{PHT_URL}/proposal-access/user/{my_access_id}",
        data=json.dumps(my_access_record),
        headers={"Content-Type": "application/json"},
    )

    updated_complete_submit_proposal = json.loads(VALID_COMPLETE_PROPOSAL)
    updated_complete_submit_proposal["prsl_id"] = prsl_id

    put_resp = authrequests.put(
        f"{PHT_URL}/prsls/{prsl_id}",
        data=json.dumps(updated_complete_submit_proposal),
        headers={"Content-Type": "application/json"},
    )
    assert put_resp.status_code == HTTPStatus.FORBIDDEN

    # Verify version increment not occured
    get_still_v1 = authrequests.get(f"{PHT_URL}/prsls/{prsl_id}")
    assert get_still_v1.status_code == HTTPStatus.OK, get_still_v1.content
    assert get_still_v1.json()["metadata"]["version"] == v1


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
        prsl_id = f"prsl-test-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.proposal(prsl_id=prsl_id)
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
    assert len(proposals) == len(
        created_ids
    ), f"Expected {len(created_ids)} proposals, got {len(proposals)}"

    returned_ids = {p["prsl_id"] for p in proposals}
    for prsl_id in created_ids:
        assert prsl_id in returned_ids, f"Missing proposal {prsl_id} in POST /batch"


def test_get_reviews_for_panel_with_wrong_id(authrequests):
    prsl_id = "wrong id"
    response = authrequests.get(f"{PHT_URL}/prsls/reviews/{prsl_id}")
    assert response.status_code == HTTPStatus.OK
    res = response.json()
    assert [] == res


def test_get_reviews_for_panel_with_valid_id(authrequests):
    proposal = TestDataFactory.complete_proposal("my proposal")
    response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=proposal.json(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK

    panel_id = "panel-test-20250717-00001"
    panel = TestDataFactory.panel_basic(panel_id=panel_id, name="New name")
    data = panel.json()
    response = authrequests.post(
        f"{PANELS_API_URL}/create",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK
    review = [
        TestDataFactory.reviews(
            prsl_id=proposal.prsl_id,
        )
    ]
    response = authrequests.post(
        f"{PHT_URL}/reviews/create",
        data=review[0].json(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK

    response = authrequests.get(f"{PHT_URL}/prsls/reviews/{proposal.prsl_id}")
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
        prsl_id = f"prsl-pending-{uuid.uuid4().hex[:8]}"
        proposal = TestDataFactory.complete_proposal(
            prsl_id=prsl_id, status=status_to_test
        )
        proposal_json = proposal.model_dump_json()

        response = authrequests.post(
            f"{PHT_URL}/prsls/create",
            data=proposal_json,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.OK, response.content
        created_ids_with_target_status.append(prsl_id)

    # Create proposals with different statuses additionally
    for status in ["draft", "rejected"]:
        prsl_id = f"prsl-{status}-{uuid.uuid4().hex[:8]}"
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
        assert (
            prsl_id in returned_ids
        ), f"Missing {prsl_id} from GET /status/{status_to_test}"

    # Other statuses should not be returned
    for prsl_id in created_ids_with_other_status:
        assert (
            prsl_id not in returned_ids
        ), f"Unexpected proposal {prsl_id} in GET /status/{status_to_test}"
