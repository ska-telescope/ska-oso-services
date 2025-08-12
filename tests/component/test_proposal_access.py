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

    proposal_access = TestDataFactory.proposal_access(access_id="access_id_test_post")
    proposal_access_json = proposal_access.model_dump_json()

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert isinstance(result, str)


def test_post_duplicate_proposal_access(authrequests):
    """
    Integration test:
    - Create multiple proposal access
    - Check for expected error the duplicated one cannot be created
    """

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_post_duplicate",
        prsl_id="prsl_id_test_post_duplicate",
        user_id="TEST_USER",
    )

    proposal_access_json = proposal_access.model_dump_json()

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK

    duplicate_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert duplicate_response.status_code == HTTPStatus.BAD_REQUEST

    result = duplicate_response.json()
    expected = {
        "detail": (
            "duplicate key value violates unique constraint "
            '"tab_oda_prsl_access_prsl_id_user_id_version_key"\n'
            "DETAIL:  Key (prsl_id, user_id, version)="
            "(prsl_id_test_post_duplicate, TEST_USER, 1) already exists."
        )
    }
    assert expected == result


def test_get_list_proposal_access_for_user(authrequests):
    """
    Integration test:
    - Create proposal access
    - Use GET /proposal-access/user to retrieve them
    - Ensure the proposal access with specific prsl_id is returned
    """

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_user",
        prsl_id="prsl_id_test_get_by_user",
        user_id=TEST_USER,
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    proposal_access_other_user = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_user",
        prsl_id="prsl_id_test_get_by_user",
        user_id="other_user",
    )

    proposal_access_other_user_json = proposal_access_other_user.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_other_user_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/user")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()

    get_result_filtered = [
        item for item in get_result if (item["prsl_id"] == "prsl_id_test_get_by_user")
    ]

    assert len(get_result_filtered) == 1


def test_get_list_proposal_access_for_prsl_id(authrequests):
    """
    Integration test:
    - Create proposal access
    - use GET /proposal-access/{prsl_id} to get a list of proposal
    - ensure the proposal access is in the list
    """

    TEST_PRSL_ID = "prsl_id_test_get_by_prsl_id"

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_prsl_id",
        prsl_id=TEST_PRSL_ID,
        user_id=TEST_USER,
        role="Principal Investigator",
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/{TEST_PRSL_ID}")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()

    print("get_response", get_response)

    get_result_filtered = [
        item for item in get_result if item["prsl_id"] == TEST_PRSL_ID
    ]

    print("get_result_filtered", get_result_filtered)

    assert len(get_result_filtered) == 1
    assert get_result_filtered[0]["prsl_id"] == TEST_PRSL_ID


def test_get_list_proposal_access_for_prsl_id_not_PI(authrequests):
    """
    Integration test:
    - Create proposal access
    - use GET /proposal-access/{prsl_id} to get a list of proposal
    - ensure the proposal access is in the list
    """

    TEST_PRSL_ID = "prsl_id_test_get_by_prsl_id_not_PI"

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_prsl_id_not_PI",
        prsl_id=TEST_PRSL_ID,
        user_id=TEST_USER,
        role="Co-Investigator",
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/{TEST_PRSL_ID}")

    print("get_response", get_response)
    assert get_response.status_code == HTTPStatus.FORBIDDEN


def test_put_proposal_access(authrequests):
    """
    Integration test:
    - Create proposal access and save access_id
    - Use PUT /proposal-access/user/{access_id} to update them
    - Ensure version is bumped
    """

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_put_proposal_access",
        prsl_id="prsl_id_test_put_proposal_access",
    )

    proposal_access_json = proposal_access.model_dump_json()

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access_json,
        headers={"Content-Type": "application/json"},
    )

    access_id = post_response.json()

    NEW_PERMISSIONS = ["view", "submit"]

    put_proposal_access = TestDataFactory.proposal_access(
        access_id=access_id,
        user_id=TEST_USER,
        role="Principal Investigator",
        prsl_id="prsl_id_test_put_proposal_access",
        permission=NEW_PERMISSIONS,
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
