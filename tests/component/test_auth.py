from http import HTTPStatus

import pytest
import requests
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.test_helpers import TEST_USER, mint_test_token

from ..unit.util import SBDEFINITION_WITHOUT_METADATA_JSON
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


def test_user_extracted_from_auth():
    token = mint_test_token(
        audience=AUDIENCE, scopes={"odt:readwrite"}, roles={Role.SW_ENGINEER}
    )
    response = requests.post(
        f"{ODT_URL}/sbds",
        data=SBDEFINITION_WITHOUT_METADATA_JSON,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-type": "application/json",
        },
    )

    result = response.json()

    assert result["metadata"]["created_by"] == TEST_USER
    assert result["metadata"]["last_modified_by"] == TEST_USER
