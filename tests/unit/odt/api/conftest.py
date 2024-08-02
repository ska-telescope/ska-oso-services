"""
pytest fixtures to be used by unit tests
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ska_oso_services import create_app


@pytest.fixture(name="test_app")
def test_app_fixture() -> FastAPI:
    """
    Fixture to configure a test app instance
    """
    return create_app(production=False)


@pytest.fixture()
def client(test_app: FastAPI) -> TestClient:
    """
    Create a test client from the app instance, without running a live server
    """
    return TestClient(test_app)
