"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS

REVIEWERS_API_URL = f"{PHT_BASE_API_URL}/reviewers"


class TestReviewersAPI:

    def test_get_reviewers(self, client):
        """
        Check the get_reviewers method returns the expected reviewers data.
        """
        response = client.get(
            f"{REVIEWERS_API_URL}",
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == REVIEWERS
