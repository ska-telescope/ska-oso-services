from http import HTTPStatus

import pytest
import requests
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from ska_oso_services.common.auth import Scope

from . import ODT_URL, OSO_SERVICES_URL
from .conftest import AUDIENCE


@pytest.mark.parametrize(
    "url,role,scope,status",
    [
        (
            f"{ODT_URL}/sbds/create",
            Role.SW_ENGINEER,
            Scope.ODT_READWRITE,
            HTTPStatus.OK,
        ),
        (f"{ODT_URL}/sbds/create", Role.ANY, Scope.ODT_READWRITE, HTTPStatus.FORBIDDEN),
        (
            f"{OSO_SERVICES_URL}/coordinates/N10/equatorial",
            Role.ANY,
            Scope.ODT_READ,
            HTTPStatus.OK,
        ),
        (
            f"{OSO_SERVICES_URL}/prsls/list/DefaultUser",
            Role.SW_ENGINEER,
            Scope.ODT_READ,
            HTTPStatus.OK,
        ),
    ],
)
def test_correct_authorization_enforced(url, role, scope, status):
    token = mint_test_token(audience=AUDIENCE, scopes={scope}, roles={role})
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status
