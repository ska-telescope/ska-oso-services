# pylint: disable=missing-timeout
import uuid
from http import HTTPStatus

from ..unit.util import TestDataFactory
from . import PHT_URL


def test_post_proposal_access(authrequests):
    """
    Integration test: TODO
    - Create multiple reviews
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created panel-decision are returned
    """

    # TEST_USER user id

    proposal_access = TestDataFactory.proposal_access(access_id="access_id_test_post")

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert proposal_access.access_id == result


def test_post_duplicate_proposal_access(authrequests):
    """
    Integration test: TODO
    - Create multiple reviews
    - Fetch created_by from one
    - Use GET /list/{user_id} to retrieve them
    - Ensure all created panel-decision are returned
    """

    # TEST_USER user id

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_post_duplicate"
    )

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK

    response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {
        "detail": (
            "duplicate key value violates unique constraint "
            '"tab_oda_prsl_access_prsl_id_user_id_version_key"\n'
            "DETAIL:  Key (prsl_id, user_id, version)="
            "(access_id_test_post_duplicate, TEST_USER, 1) already exists."
        )
    }
    assert expected == result


def test_get_list_proposal_access_for_user(authrequests):
    """
    Integration test: TODO
    - Create multiple panels
    - Fetch created_by from one
    - Use GET /{user_id} to retrieve them
    - Ensure all created panels are returned
    """

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_user", prsl_id="prsl_id_test_get_by_user"
    )

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/user")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()
    get_result_filtered = [
        item for item in get_result if item["prsl_id"] == "prsl_id_test_get_by_user"
    ]
    assert get_result_filtered.length == 1


def test_get_list_proposal_access_for_prsl_id(authrequests):
    """
    Integration test: TODO
    - Create multiple panels
    - Fetch created_by from one
    - Use GET /{user_id} to retrieve them
    - Ensure all created panels are returned
    """

    TEST_PRSL_ID = "prsl_id_test_get_by_prsl_id"

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_get_by_prsl_id", prsl_id=TEST_PRSL_ID
    )

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert post_response.status_code == HTTPStatus.OK

    get_response = authrequests.get(f"{PHT_URL}/proposal-access/user/{TEST_PRSL_ID}")

    assert get_response.status_code == HTTPStatus.OK

    get_result = get_response.json()
    get_result_filtered = [
        item for item in get_result if item["prsl_id"] == TEST_PRSL_ID
    ]
    assert get_result_filtered.length == 1


def test_put_proposal_access(authrequests):
    """
    Integration test: TODO
    - Create multiple panels
    - Fetch created_by from one
    - Use GET /{user_id} to retrieve them
    - Ensure all created panels are returned
    """

    proposal_access = TestDataFactory.proposal_access(
        access_id="access_id_test_put_proposal_access"
    )

    post_response = authrequests.post(
        f"{PHT_URL}/proposal-access/prslacl",
        data=proposal_access,
        headers={"Content-Type": "application/json"},
    )

    access_id = post_response.json()

    NEW_PERMISSON = ["view", "submit"]

    put_proposal_access = TestDataFactory.proposal_access(
        access_id=access_id, permission=NEW_PERMISSON
    )

    put_response = authrequests.put(
        f"{PHT_URL}/proposal-access/user/{access_id}",
        data=put_proposal_access,
        headers={"Content-Type": "application/json"},
    )

    assert put_response.status_code == HTTPStatus.OK

    put_result = put_response.json()

    assert put_result["metadata"]["version"] == 2
    assert put_result["permisson"] == NEW_PERMISSON
