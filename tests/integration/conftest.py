import base64
import time
from collections.abc import Generator
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token, monkeypatch_pubkeys
from testcontainers.core.container import DockerContainer

from ska_oso_services.settings import get_settings
from tests.conftest import FAKE_USER_PORTAL_PORT

USER_PORTAL_FIXTURE_SPEC = (
    Path(__file__).resolve().parents[1] / "fixtures" / "user-portal.openapi.yaml"
)
PRISM_IMAGE = "docker.io/stoplight/prism:latest"


@pytest.fixture(scope="session")
def fake_user_portal() -> Generator[DockerContainer, None, None]:
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
                f"-h 0.0.0.0 -p {FAKE_USER_PORTAL_PORT} "
                "--no-multiprocess /tmp/user-portal.openapi.yaml"
            )
        ]
    )
    container.with_bind_ports(FAKE_USER_PORTAL_PORT, FAKE_USER_PORTAL_PORT)

    with container as prism:
        portal_base = get_settings().user_portal_base_url
        probe_url = f"{portal_base}/api/external/v1/users/search?q=test"
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

        yield prism


@pytest.fixture(scope="session")
def integration_headers() -> dict[str, str]:
    # lazy import so that pytest_configure() can set env vars first
    from ska_oso_services.common.auth import Scope

    token = mint_test_token(
        audience="test:pht",
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
    # lazy import so that pytest_configure() can set env vars first
    from ska_oso_services import create_app

    app = create_app(production=False)
    with TestClient(app, headers=integration_headers) as client:
        yield client
