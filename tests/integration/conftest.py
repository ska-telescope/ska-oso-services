import base64
import os
import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token, monkeypatch_pubkeys
from testcontainers.core.container import DockerContainer

TEST_AUDIENCE = os.environ.get("SKA_AUTH_AUDIENCE", "test:pht")
# Ensure auth audience is set before importing modules that bind auth configuration at import time.
os.environ["SKA_AUTH_AUDIENCE"] = TEST_AUDIENCE
os.environ.setdefault("USER_PORTAL_BASE_URL", "https://userportal.skao.int.example")

from ska_oso_services import create_app
from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.service import user_portal
from tests.conftest import TEST_BASE_API_URL

USER_PORTAL_FIXTURE_SPEC = (
    Path(__file__).resolve().parents[1] / "fixtures" / "user-portal.openapi.yaml"
)
PRISM_IMAGE = "docker.io/stoplight/prism:latest"
PRISM_CONTAINER_PORT = 4010
PRISM_HOST_PORT = 60517
PHT_BASE_URL = f"{TEST_BASE_API_URL}/pht"


@pytest.fixture(scope="session")
def prism_user_portal_base_url() -> Generator[str, None, None]:
    """
    Start a Prism mock in Docker from the checked-in OpenAPI fixture.
    """
    if not USER_PORTAL_FIXTURE_SPEC.exists():
        pytest.fail(f"Missing OpenAPI fixture: {USER_PORTAL_FIXTURE_SPEC}")

    spec_b64 = base64.b64encode(USER_PORTAL_FIXTURE_SPEC.read_bytes()).decode("ascii")

    container = DockerContainer(PRISM_IMAGE)
    # Inject the spec at startup so this works with remote Docker daemons (for example minikube).
    container.with_env("USER_PORTAL_OPENAPI_B64", spec_b64)
    container.with_kwargs(entrypoint=["sh", "-lc"])
    container.with_command(
        [
            (
                "node -e \"require('fs').writeFileSync('/tmp/user-portal.openapi.yaml', "
                "Buffer.from(process.env.USER_PORTAL_OPENAPI_B64, 'base64'))\" "
                "&& exec node /usr/src/prism/packages/cli/dist/index.js mock "
                "-h 0.0.0.0 -p 4010 --no-multiprocess /tmp/user-portal.openapi.yaml"
            )
        ]
    )
    container.with_bind_ports(PRISM_CONTAINER_PORT, PRISM_HOST_PORT)

    with container:
        base_url = f"http://localhost:{PRISM_HOST_PORT}"
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


@pytest.fixture
def user_portal_base_url(prism_user_portal_base_url):
    with mock.patch.object(user_portal, "USER_PORTAL_BASE_URL", prism_user_portal_base_url):
        yield prism_user_portal_base_url


@pytest.fixture(scope="session")
def integration_headers() -> dict[str, str]:
    token = mint_test_token(
        audience=TEST_AUDIENCE,
        user_id=str(uuid4()),
        roles=[
            Role.ANY,
            Role.OPS_PROPOSAL_ADMIN,
            Role.OPS_REVIEWER_SCIENCE,
            Role.OPS_REVIEWER_TECHNICAL,
            Role.SW_ENGINEER,
        ],
        scopes=[
            Scope.PHT_READ,
            Scope.PHT_READWRITE,
            Scope.PHT_UPDATE,
        ],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def patch_pubkeys_for_integration():
    monkeypatch_pubkeys()


@pytest.fixture
def integration_client(
    integration_headers,
):
    app = create_app(production=False)
    with TestClient(app, headers=integration_headers) as client:
        yield client
