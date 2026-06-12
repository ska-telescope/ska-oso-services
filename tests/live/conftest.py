"""
Fixtures for live Indigo IAM smoke tests.

These credentials are non-secret defaults for an isolated staging environment.
Override any value via the corresponding environment variable.
"""
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from importlib.metadata import version
from ska_aaa_authhelpers.test_helpers import TEST_AUDIENCE

from ska_oso_services import create_app

INDIGO_IAM_TOKEN_URL = "https://iam-1.staging.devx.skao.int/token"
DEFAULT_CLIENT_ID = "436915fe-7d98-487a-93b2-b3d5f9bc5952"
DEFAULT_CLIENT_SECRET = (
    "AOzHcqR2tz5sfZSOPmuQ4CU6VDQmUSSJCHZLEpMUHhRADvhh4og_XD8SNDGVI4uYA4QN_QVS4nS9AB_tT9IQd-0"
)
DEFAULT_USERNAME = "ska-login-page-integration-test-user"
DEFAULT_PASSWORD = "TestPassw0rd!"

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
PHT_BASE_API_URL = f"/ska-oso-services/oso/api/v{OSO_SERVICES_MAJOR_VERSION}/pht"


@pytest.fixture(scope="session")
def indigo_token() -> str:
    """Fetch a real access token from the staging Indigo IAM instance."""
    client_id = os.environ.get("INDIGO_TEST_CLIENT_ID", DEFAULT_CLIENT_ID)
    client_secret = os.environ.get("INDIGO_TEST_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
    audience = os.environ.get("SKA_AUTH_AUDIENCE", "test:pht")

    data = {
        "grant_type": "password",
        "username": os.environ.get("INDIGO_TEST_USERNAME", DEFAULT_USERNAME),
        "password": os.environ.get("INDIGO_TEST_PASSWORD", DEFAULT_PASSWORD),
        "scope": "openid profile pht:read pht:readwrite",
        "audience": audience,
    }
    response = httpx.post(
        INDIGO_IAM_TOKEN_URL,
        data=data,
        auth=(client_id, client_secret),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def live_client() -> TestClient:
    """
    TestClient with no key monkeypatching — real Indigo JWKS are fetched
    and token signatures verified against them.
    """
    app = create_app(production=False)
    return TestClient(app)
