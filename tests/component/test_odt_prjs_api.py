"""
Component level tests for the /oda/prjs paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

import json

# pylint: disable=missing-timeout
from http import HTTPStatus

from ..unit.util import TestDataFactory, assert_json_is_equal
from . import ODT_URL


class TestLinkingSBDefinitions:
    """Tests of the /prjs subroutes that concern creating and linking SBDefinitions"""

    def test_sbd_created_and_linked_to_project(self, authrequests):
        """
        Test that an entity sent to POST /prjs creates an empty project, then a request
        to POST /prjs/<prj_id>/<obs_block_id>/sbds with an SBDefinition in the request body
        adds that SBDefinition to the Project
        """
        # Create an empty Project
        prj_post_response = authrequests.post(f"{ODT_URL}/prjs")

        assert prj_post_response.status_code == HTTPStatus.OK, prj_post_response.content
        prj_id = prj_post_response.json()["prj_id"]
        obs_block_id = prj_post_response.json()["obs_blocks"][0]["obs_block_id"]

        # Create an SBDefinition in that Project in the first observing block
        sbd_post_response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/{obs_block_id}/sbds",
            data=json.dumps({"telescope": "ska_mid"}),
            headers={"Content-type": "application/json"},
        )
        assert sbd_post_response.status_code == HTTPStatus.OK, sbd_post_response.text
        assert sbd_post_response.json()["sbd"]["telescope"] == "ska_mid"

        sbd_id = sbd_post_response.json()["sbd"]["sbd_id"]
        get_sbd_response = authrequests.get(f"{ODT_URL}/sbds/{sbd_id}")
        assert get_sbd_response.status_code == HTTPStatus.OK
        assert get_sbd_response.json()["ob_ref"] == obs_block_id

        # Check the SBDefinition is resolved when getting Project
        get_prj_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")
        assert get_prj_response.status_code == HTTPStatus.OK, get_prj_response.content
        assert get_prj_response.json()["obs_blocks"][0]["sbd_ids"][0] == sbd_id

    def test_project_not_found_raises_error(self, authrequests):
        prj_id = "not-a-prj"
        response = authrequests.post(
            f"{ODT_URL}/prjs/{prj_id}/ob-123/sbds",
            data=json.dumps({"telescope": "ska_mid"}),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND, response.content
        assert (
            response.json()["detail"] == f"The requested identifier {prj_id} could not be found."
        )

    def test_ob_not_in_project_raises_error(self, authrequests, test_project):
        ob_id = "not-an-ob"
        response = authrequests.post(
            f"{ODT_URL}/prjs/{test_project.prj_id}/{ob_id}/sbds",
            data=json.dumps({"telescope": "ska_mid"}),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND, response.content
        assert response.json()["detail"] == f"Observing Block '{ob_id}' not found in Project"

    def test_inconsistent_ob_ref_raises_error(self, authrequests, test_project):
        response = authrequests.post(
            f"{ODT_URL}/prjs/{test_project.prj_id}/{test_project.obs_blocks[0].obs_block_id}/sbds",
            data=json.dumps({"telescope": "ska_mid", "ob_ref": "different-ob"}),
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert (
            response.json()["detail"]
            == "ob_ref in SBDefinition body does not match the request URL"
        )


class TestProjectAPI:
    """Tests of the standard methods on the /prjs route"""

    def test_prj_post_then_get(self, authrequests):
        """
        Test that an entity sent to POST /prjs can then be retrieved
        with GET /prjs/{identifier}
        """
        project_json = TestDataFactory.project(prj_id=None).model_dump_json()
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project_json,
            headers={"Content-type": "application/json"},
        )

        assert post_response.status_code == HTTPStatus.OK, post_response.content
        assert_json_is_equal(
            post_response.content,
            project_json,
            exclude_paths=[
                "root['metadata']",
                "root['prj_id']",
                "root['obs_blocks'][0]['obs_block_id']",
                "root['obs_blocks'][1]['obs_block_id']",
            ],
        )

        prj_id = post_response.json()["prj_id"]
        get_response = authrequests.get(f"{ODT_URL}/prjs/{prj_id}")

        # Assert the ODT can get the Project, ignoring the metadata as it contains
        # timestamps and is the responsibility of the ODA

        assert get_response.status_code == HTTPStatus.OK, get_response.content
        assert_json_is_equal(
            get_response.content,
            project_json,
            exclude_paths=[
                "root['metadata']",
                "root['prj_id']",
                "root['obs_blocks'][0]['obs_block_id']",
                "root['obs_blocks'][1]['obs_block_id']",
            ],
        )

    def test_prj_post_then_put(self, authrequests):
        """
        Test that an entity sent to POST /prjs can then be
        updated with PUT /prjs/{identifier} - this tests an OB can be added
        """
        project = TestDataFactory.project(prj_id=None)
        project_json = project.model_dump_json()
        post_response = authrequests.post(
            f"{ODT_URL}/prjs",
            data=project_json,
            headers={"Content-type": "application/json"},
        )

        assert post_response.status_code == HTTPStatus.OK, post_response.content
        assert_json_is_equal(
            post_response.content,
            project_json,
            exclude_paths=["root['metadata']", "root['prj_id']"],
        )

        prj_id = post_response.json()["prj_id"]
        project.prj_id = prj_id
        project.obs_blocks.append(TestDataFactory.project(prj_id=prj_id).obs_blocks[0])
        updated_project_json = project.model_dump_json()

        put_response = authrequests.put(
            f"{ODT_URL}/prjs/{prj_id}",
            data=updated_project_json,
            headers={"Content-type": "application/json"},
        )
        # Assert the ODT can get the Project, ignoring the metadata as it contains
        # timestamps and is the responsibility of the ODA
        assert put_response.status_code == HTTPStatus.OK, put_response.content
        assert_json_is_equal(
            put_response.content,
            updated_project_json,
            exclude_paths=["root['metadata']", "root['prj_id']"],
        )
        assert put_response.json()["metadata"]["version"] == 2

    def test_prj_get_not_found(self, authrequests):
        """
        Test that the GET /prjs/{identifier} path returns
        404 when the Project is not found in the ODA
        """

        response = authrequests.get(f"{ODT_URL}/prjs/123")

        assert response.status_code == HTTPStatus.NOT_FOUND, response.content
        assert response.json()["detail"] == "The requested identifier 123 could not be found."

    def test_prj_put_not_found(self, authrequests):
        """
        Test that the GET /prjs/{identifier} path returns
        404 when the Project is not found in the ODA
        """

        response = authrequests.get(f"{ODT_URL}/prjs/123")

        assert response.status_code == HTTPStatus.NOT_FOUND, response.content
        assert response.json()["detail"] == "The requested identifier 123 could not be found."
