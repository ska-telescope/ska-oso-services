"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus
from unittest import mock

import pytest
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from ska_oso_services.common.auth import Scope

from tests.conftest import PHT_BASE_API_URL

REVIEWERS_API_URL = f"{PHT_BASE_API_URL}/reviewers"


class TestGetReviewersEndpoint:
    def test_get_reviewers_not_implemented(self, client):
        token = mint_test_token(
            audience="test:pht",
            roles=[Role.INTERNAL],
            scopes=[Scope.PHT_READ],
            groups=["app:pht:ops_proposal_admin"],
        )
        response = client.get(
            f"{REVIEWERS_API_URL}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == HTTPStatus.NOT_IMPLEMENTED
        assert response.json() == {"detail": "Not Implemented"}
