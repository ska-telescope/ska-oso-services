"""
pytest fixtures to be used by unit tests
"""

from importlib.metadata import version

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ska_oso_services import create_app

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
PHT_BASE_API_URL = f"/ska-oso-services/oso/api/v{OSO_SERVICES_MAJOR_VERSION}/pht"


@pytest.fixture()
def client(test_app: FastAPI) -> TestClient:
    """
    Create a test client from the app instance, without running a live server
    """
    return TestClient(test_app)
