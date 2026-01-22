# pylint: disable=missing-timeout
from http import HTTPStatus

from ska_aaa_authhelpers.test_helpers.constants import TEST_USER

from ..unit.util import TestDataFactory
from . import PHT_URL


def test_post_proposal_access(authrequests):
    """
    Integration test:
    - Create a proposal access
    - Ensure it returns an id
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_post", prsl_id=prsl_id
    )
    proposal_access_json = proposal_access.model_dump_json()

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK, response.text

    result = response.json()
    assert isinstance(result, str)


def test_get_list_proposal_access_for_user(authrequests):
    """
    Integration test:
    - Create proposal access
    - Use GET /proposal-access/user to retrieve them
    - Ensure the proposal access with specific prsl_id is returned
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_user",
        prsl_id=prsl_id,
        user_id=TEST_USER,
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    proposal_access_other_user = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_user",
        prsl_id=prsl_id,
        user_id="other_user",
    )

    proposal_access_other_user_json = proposal_access_other_user.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_other_user_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/user")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()

    get_result_filtered = [item for item in get_result if (item["prsl_id"] == prsl_id)]

    assert len(get_result_filtered) == 1


def test_get_list_proposal_access_for_prsl_id(authrequests):
    """
    Integration test:
    - Create proposal access
    - use GET /proposal-access/{prsl_id} to get a list of proposal
    - ensure the proposal access is in the list
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_prsl_id",
        prsl_id=prsl_id,
        user_id=TEST_USER,
        role="Principal Investigator",
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/{prsl_id}")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()

    get_result_filtered = [item for item in get_result if item["prsl_id"] == prsl_id]

    assert len(get_result_filtered) == 1
    assert get_result_filtered[0]["prsl_id"] == prsl_id


def test_get_list_proposal_access_for_prsl_id_not_PI(authrequests):
    """
    Integration test:
    - Create proposal access
    - use GET /proposal-access/{prsl_id} to get a list of proposal
    - ensure the proposal access is in the list
    """

    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_prsl_id_not_PI",
        prsl_id=prsl_id,
        user_id=TEST_USER,
        role="Co-Investigator",
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/{prsl_id}")

    assert get_response.status_code == HTTPStatus.FORBIDDEN


def test_put_proposal_access(authrequests):
    """
    Integration test:
    - Create proposal access and save access_id
    - Use PUT /proposal-access/user/{access_id} to update them
    - Ensure version is bumped
    """
    # Add proposal to link to
    post_response = authrequests.post(
        f"{PHT_URL}/prsls/create",
        data=TestDataFactory.proposal(prsl_id=None).model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    assert post_response.status_code == HTTPStatus.OK, post_response.text
    prsl_id = post_response.json()["prsl_id"]

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_put_proposal_access",
        prsl_id=prsl_id,
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/create",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    access_id = post_response.json()

    NEW_PERMISSIONS = ["view", "submit"]

    put_proposal_access = TestDataFactory.proposal_access(
        access_id=access_id,
        user_id=TEST_USER,
        role="Principal Investigator",
        prsl_id=prsl_id,
        permissions=NEW_PERMISSIONS,
    )

    put_proposal_access_json = put_proposal_access.model_dump_json()

    put_response = authrequests.put(
        f"{PHT_URL}/proposal-access/user/{access_id}",
        data=put_proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert put_response.status_code == HTTPStatus.OK

    put_result = put_response.json()

    assert put_result["metadata"]["version"] == 2
    assert put_result["permissions"] == NEW_PERMISSIONS
