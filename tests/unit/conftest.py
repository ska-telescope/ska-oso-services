"""
pytest fixtures to be used by unit tests
"""

from functools import partial
from importlib.metadata import version
from pathlib import Path

import pytest
from astropy.io import ascii
from astropy.table import QTable
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token, monkeypatch_pubkeys

from ska_oso_services import create_app
from ska_oso_services.common.auth import AUDIENCE, Scope
from ska_oso_services.pht.models.domain import PrslRole

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
APP_BASE_API_URL = f"/ska-oso-services/oso/api/v{OSO_SERVICES_MAJOR_VERSION}"
ODT_BASE_API_URL = f"{APP_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{APP_BASE_API_URL}/pht"


@pytest.fixture(scope="module")
def dummy_calibrator_table() -> QTable:
    """
    Fixture to create a dummy table so the tests won't fail if a new calibrator is added
    """
    path_to_test_table = (
        Path(__file__).parents[0] / "files" / "dummy_calibrator_table.ecsv"
    )
    return ascii.read(path_to_test_table)


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
    token = mint_test_token(
        audience=AUDIENCE,
        roles=[
            Role.ANY,
            Role.OPS_PROPOSAL_ADMIN,
            Role.OPS_REVIEWER_SCIENCE,
            Role.OPS_REVIEWER_TECHNICAL,
            Role.SW_ENGINEER,
        ],
        scopes=[
            Scope.ODT_READWRITE,
            Scope.ODT_READ,
            Scope.PHT_READ,
            Scope.PHT_READWRITE,
        ],
        groups=[Role.OPS_PROPOSAL_ADMIN, PrslRole.OPS_REVIEW_CHAIR],
    )
    headers = {"Authorization": f"Bearer {token}"}
    return TestClient(test_app, headers=headers)


@pytest.fixture(scope="module")
def client_get(client: TestClient):  # pylint: disable=redefined-outer-name
    """Always call GET with the client’s default auth headers."""
    return partial(client.get, headers=client.headers)


@pytest.fixture(scope="session", autouse=True)
def patch_pubkeys():
    monkeypatch_pubkeys()
