"""k8s smoke-test fixtures.

These tests exercise a *deployed* ska-oso-services release (Helm chart +
image + Postgres + networking).  They do **not** start a testcontainer —
that's what the suites under ``tests/component/`` are for.

The deployed service URL is supplied via the ``OSO_SERVICES_URL``
environment variable (the Makefile's ``k8s-test`` target sets it).
"""

import os
from http import HTTPStatus
from importlib.metadata import version

import pytest
import requests
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

OSO_SERVICES_URL = os.environ.get("OSO_SERVICES_URL")
AUDIENCE = os.environ.get("SKA_AUTH_AUDIENCE", "test:pht")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]


@pytest.fixture(scope="session")
def service_url() -> str:
    if not OSO_SERVICES_URL:
        pytest.fail(
            "OSO_SERVICES_URL is not set.  The k8s smoke suite must be run "
            "against a deployed service — see the `k8s-test` Makefile target."
        )
    return OSO_SERVICES_URL


@pytest.fixture(scope="session")
def auth_headers() -> dict:
    """Bearer token with the same role/scope set used by component tests."""
    token = mint_test_token(
        audience=AUDIENCE,
        roles=[
            Role.ANY,
            Role.OPS_PROPOSAL_ADMIN,
            Role.OPS_REVIEWER_SCIENCE,
            Role.OPS_REVIEWER_TECHNICAL,
            Role.SW_ENGINEER,
        ],
        scopes=["odt:readwrite", "odt:read", "pht:read", "pht:readwrite"],
    )
    return {"Authorization": f"Bearer {token}"}


def _expect_ok(response: requests.Response) -> None:
    assert response.status_code == HTTPStatus.OK, (
        f"{response.request.method} {response.request.url} returned "
        f"{response.status_code}: {response.text}"
    )
