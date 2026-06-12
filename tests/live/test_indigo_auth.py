"""
Smoke tests: verify a real Indigo IAM token is accepted by PHT endpoints.
Requires live network access to the staging Indigo IAM instance.
Run via: pytest tests/live/ -m live
"""
from http import HTTPStatus
from unittest import mock

import pytest

from tests.live.conftest import PHT_BASE_API_URL

pytestmark = pytest.mark.live


@mock.patch("ska_oso_services.pht.api.reviews.oda.uow")
def test_indigo_token_accepted_for_reviews(mock_uow, live_client, indigo_token):
    """Real Indigo token with pht:read is accepted at GET /reviews/users/reviews."""
    mock_uow.return_value.__enter__.return_value.rvws.query.return_value = []

    response = live_client.get(
        f"{PHT_BASE_API_URL}/reviews/users/reviews",
        headers={"Authorization": f"Bearer {indigo_token}"},
    )

    assert response.status_code == HTTPStatus.OK


@mock.patch("ska_oso_services.pht.api.prsls.oda.uow")
def test_indigo_token_accepted_for_proposals(mock_uow, live_client, indigo_token):
    """Real Indigo token with pht:read is accepted at GET /prsls/mine."""
    mock_uow.return_value.__enter__.return_value.prslacc.query.return_value = []

    response = live_client.get(
        f"{PHT_BASE_API_URL}/prsls/mine",
        headers={"Authorization": f"Bearer {indigo_token}"},
    )

    assert response.status_code == HTTPStatus.OK
