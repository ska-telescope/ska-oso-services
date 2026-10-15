"""
Fixtures for live tests against staging Indigo IAM and the staging User Portal.

These credentials are non-secret defaults for an isolated staging environment.
Override any value via the corresponding environment variable.
"""

import base64
import json
import os
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import FAKE_USER_PORTAL_CLIENT_SECRET

INDIGO_IAM_TOKEN_URL = "https://iam-1.staging.devx.skao.int/token"
DEFAULT_CLIENT_ID = "436915fe-7d98-487a-93b2-b3d5f9bc5952"
DEFAULT_CLIENT_SECRET = (
    "AOzHcqR2tz5sfZSOPmuQ4CU6VDQmUSSJCHZLEpMUHhRADvhh4og_XD8SNDGVI4uYA4QN_QVS4nS9AB_tT9IQd-0"
)
DEFAULT_USERNAME = "ska-login-page-integration-test-user"
DEFAULT_PASSWORD = "TestPassw0rd!"


@pytest.fixture(scope="module")
def indigo_token() -> str:
    """Fetch a real access token from the staging Indigo IAM instance."""
    client_id = os.environ.get("INDIGO_TEST_CLIENT_ID", DEFAULT_CLIENT_ID)
    client_secret = os.environ.get("INDIGO_TEST_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
    # SKA_AUTH_AUDIENCE may list several audiences the app accepts; request the first
    audience = os.environ.get("SKA_AUTH_AUDIENCE", "test:pht").split(",")[0].strip()

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
    # lazy import so that pytest_configure() can set env vars first
    from ska_oso_services import create_app

    app = create_app(production=False)
    return TestClient(app)


def unverified_claims(token: str) -> dict:
    """Read a JWT's claims without verifying it, e.g. to find out who a test token is for."""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


@pytest.fixture
def user_portal():
    """
    A UserPortalService using the real client-credentials grant, configured from
    the USER_PORTAL_* environment (e.g. ``uv run --env-file .env pytest tests/live``).
    """
    if os.environ.get("USER_PORTAL_CLIENT_SECRET") in (None, "", FAKE_USER_PORTAL_CLIENT_SECRET):
        pytest.skip("USER_PORTAL_* settings for the staging User Portal are not configured")

    # lazy import so that pytest_configure() can set env vars first
    from ska_oso_services.pht.service.user_portal import UserPortalService

    return UserPortalService(x_request_id=f"live-test-{uuid4()}")
