"""
pytest fixtures to be used by unit tests
"""

from importlib.metadata import version

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ska_aaa_authhelpers.test_helpers import mint_test_token, monkeypatch_pubkeys

from ska_oso_services import create_app
from ska_oso_services.common.auth import AUDIENCE, Scope

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
APP_BASE_API_URL = f"/ska-oso-services/oso/api/v{OSO_SERVICES_MAJOR_VERSION}"
ODT_BASE_API_URL = f"{APP_BASE_API_URL}/odt"


@pytest.fixture(scope="module", name="test_app")
def test_app_fixture() -> FastAPI:
    """
    Fixture to configure a test app instance
    """
    return create_app(production=False)


@pytest.fixture(scope="module")
def client(test_app: FastAPI) -> TestClient:
    """
    Create a test client from the app instance, without running a live server
    """
    token = mint_test_token(audience=AUDIENCE, scopes={Scope.ODT_READWRITE})
    headers = {"Authorization": f"Bearer {token}"}
    return TestClient(test_app, headers=headers)


@pytest.fixture(scope="session", autouse=True)
def patch_pubkeys():
    monkeypatch_pubkeys()
