import os
from unittest import mock

import pytest

TEST_BASE_API_URL = "/ska-oso-services/oso/api/v0"
ODT_BASE_API_URL = f"{TEST_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{TEST_BASE_API_URL}/pht"


@pytest.fixture(scope="session")
def mock_api_path_prefix():
    with mock.patch.dict(os.environ, {"API_PATH_PREFIX": TEST_BASE_API_URL}):
        yield
