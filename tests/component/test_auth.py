from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.test_helpers import TEST_USER, mint_test_token

from ska_oso_services import create_app

from ..unit.util import VALID_PROJECT_WITHOUT_ID_JSON
from . import ODT_BASE_API_URL, OSO_SERVICES_BASE_API_URL
from .conftest import AUDIENCE


@pytest.fixture(name="unauth_client")
def unauth_client_fixture(clean_db) -> TestClient:  # pylint: disable=unused-argument
    """TestClient with no default Authorization header — tests provide their own."""
    return TestClient(create_app(production=False))


@pytest.mark.parametrize(
    "url,role,status",
    [
        (f"{ODT_BASE_API_URL}/sbds/create", Role.SW_ENGINEER, HTTPStatus.OK),
        (f"{ODT_BASE_API_URL}/sbds/create", Role.ANY, HTTPStatus.FORBIDDEN),
        (
            f"{OSO_SERVICES_BASE_API_URL}/coordinates/N10/equatorial",
            Role.ANY,
            HTTPStatus.OK,
        ),
    ],
)
def test_correct_authorization_enforced(unauth_client, url, role, status):
    token = mint_test_token(audience=AUDIENCE, scopes={"odt:readwrite"}, roles={role})
    response = unauth_client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status


def test_user_extracted_from_auth(unauth_client):
    token = mint_test_token(
        audience=AUDIENCE, scopes={"odt:readwrite"}, roles={Role.SW_ENGINEER}
    )
    response = unauth_client.post(
        f"{ODT_BASE_API_URL}/prjs",
        content=VALID_PROJECT_WITHOUT_ID_JSON,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-type": "application/json",
        },
    )

    result = response.json()

    assert result["metadata"]["created_by"] == TEST_USER
    assert result["metadata"]["last_modified_by"] == TEST_USER
