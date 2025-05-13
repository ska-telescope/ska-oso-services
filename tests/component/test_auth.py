from http import HTTPStatus

import pytest
import requests
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from . import ODT_URL, OSO_SERVICES_URL
from .conftest import AUDIENCE


@pytest.mark.parametrize(
    "url,role,status",
    [
        (f"{ODT_URL}/sbds/create", Role.SW_ENGINEER, HTTPStatus.OK),
        (f"{ODT_URL}/sbds/create", Role.ANY, HTTPStatus.FORBIDDEN),
        (f"{OSO_SERVICES_URL}/coordinates/N10/equatorial", Role.ANY, HTTPStatus.OK),
    ],
)
def test_correct_authorization_enforced(url, role, status):
    token = mint_test_token(audience=AUDIENCE, scopes={"odt:readwrite"}, roles={role})
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status
