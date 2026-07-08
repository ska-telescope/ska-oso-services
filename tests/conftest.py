import os
import time
from pathlib import Path
from typing import Generator
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest
from testcontainers import DockerContainer

TEST_BASE_API_URL = "/ska-oso-services/oso/api/v0"
ODT_BASE_API_URL = f"{TEST_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{TEST_BASE_API_URL}/pht"
USER_PORTAL_FIXTURE_SPEC = Path(__file__).parent / "fixtures" / "user-portal.openapi.yaml"
PRISM_IMAGE = "docker.io/stoplight/prism:latest"
FAKE_USER_PORTAL_PORT = 60517
FAKE_USER_PORTAL_URL = f"http://localhost:{FAKE_USER_PORTAL_PORT}"

def pytest_configure():
    # Set test defaults early so settings created during module imports use these values.
    os.environ.setdefault("API_PATH_PREFIX", TEST_BASE_API_URL)
    os.environ.setdefault("SKA_AUTH_AUDIENCE", "test:pht,test:odt")
    os.environ.setdefault("USER_PORTAL_BASE_URL", FAKE_USER_PORTAL_URL)
    os.environ.setdefault(
        "SDP_SCRIPT_TMDATA",
        f"file://{os.path.join(os.path.dirname(__file__), 'tmdata')}",
    )

@pytest.fixture(scope="session")
def prism_user_portal_base_url() -> Generator[str, None, None]:
    """
    Start a local Prism mock in Docker from the checked-in OpenAPI fixture.
    """
    if not USER_PORTAL_FIXTURE_SPEC.exists():
        pytest.fail(f"Missing OpenAPI fixture: {USER_PORTAL_FIXTURE_SPEC}")

    container = DockerContainer(PRISM_IMAGE)
    container.with_volume_mapping(str(USER_PORTAL_FIXTURE_SPEC), "/tmp/user-portal.openapi.yaml", "ro")
    container.with_command(
        [
            "mock",
            "-h",
            "0.0.0.0",
            "-p",
            str(FAKE_USER_PORTAL_PORT),
            "--no-multiprocess",
            "/tmp/user-portal.openapi.yaml",
        ]
    )
    container.with_exposed_ports(FAKE_USER_PORTAL_PORT)

    with container:
        base_url = FAKE_USER_PORTAL_URL
        probe_url = f"{base_url}/api/external/v1/users/search?q=test"
        deadline = time.time() + 30
        ready = False
        while time.time() < deadline:
            try:
                with urlopen(probe_url, timeout=1) as response:
                    if response.status == 200:
                        ready = True
                        break
            except HTTPError as error:
                if error.code == 422:
                    ready = True
                    break
            except (ConnectionResetError, OSError, URLError):
                time.sleep(0.2)

        if not ready:
            pytest.fail("Timed out waiting for Prism mock container")

        yield base_url
