"""
Unit tests for ska_oso_pht_services.api
"""

import json
from http import HTTPStatus

from tests.unit.conftest import PHT_BASE_API_URL

REVIEWERS_API_URL = f"{PHT_BASE_API_URL}/reviewers"


class TestReviewersAPI:

    def test_get_reviewers(self, client):
        """
        Check the get_reviewers method returns the expected reviewers data.
        """
        response = client.post(
            f"{REVIEWERS_API_URL}",
            headers={"Content-type": "application/json"},
        )

        with open("tests/unit/files/get_reviewers.json", "r") as file:
            data = json.load(file)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == data
