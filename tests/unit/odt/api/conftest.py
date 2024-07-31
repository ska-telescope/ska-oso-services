"""
pytest fixtures to be used by unit tests
"""

import pytest
from fastapi.testclient import TestClient

from ska_oso_services import create_app


@pytest.fixture()
def test_app():  # pylint: disable=redefined-outer-name
    """
    Fixture to configure a test app instance
    """
    return create_app(debug=True)


@pytest.fixture()
def client(test_app):  # pylint: disable=redefined-outer-name
    """
    Create a test client from the app instance, without running a live server
    """
    return TestClient(create_app())
