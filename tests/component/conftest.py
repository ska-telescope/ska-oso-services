# pylint: disable=redefined-outer-name
"""Component-test fixtures.

These tests drive the FastAPI app in-process via ``TestClient`` against a real
Postgres started by the ``postgres_container`` fixture from
``tests/db_fixtures.py``.  No Kubernetes / minikube deployment is required.
"""

import contextlib
from enum import Enum
from os import getenv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token, monkeypatch_pubkeys
from ska_oso_pdm import Project, Proposal, SBDefinition

from ska_oso_services import create_app
from tests.component import ODT_BASE_API_URL, PHT_BASE_API_URL

from ..unit.util import TestDataFactory

# Point telmodel at the in-repo tmdata directory so SBDefinition generation
# does not need network access to gitlab.  Same path tests/unit/odt/api/
# test_sdp.py uses.
_TMDATA_PATH = (Path(__file__).resolve().parents[1] / "tmdata").as_uri()

AUDIENCE = getenv("SKA_AUTH_AUDIENCE", "test:pht")

TENANT_ID = "78887040-bad7-494b-8760-88dcacfb3805"
CLIENT_ID = "e4d6bb9b-cdd0-46c4-b30a-d045091b501b"
CLIENT_SECRET = getenv("OSO_CLIENT_SECRET", "OSO_CLIENT_SECRET")
SCOPE = ["https://graph.microsoft.com/.default"]

SECOND_TEST_USER = "12d14d12-72ae-4cc3-a806-d00ba1d2731a"


class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"


_FULL_ROLES = [
    Role.ANY,
    Role.OPS_PROPOSAL_ADMIN,
    Role.OPS_REVIEWER_SCIENCE,
    Role.OPS_REVIEWER_TECHNICAL,
    Role.SW_ENGINEER,
]
_FULL_SCOPES = [
    Scope.ODT_READWRITE,
    Scope.ODT_READ,
    Scope.PHT_READ,
    Scope.PHT_READWRITE,
]


def _mint_full_access_token(user_id: str | None = None) -> str:
    """Mint a JWT with the full set of roles/scopes used by the tests."""
    kwargs = {
        "audience": AUDIENCE,
        "roles": _FULL_ROLES,
        "scopes": _FULL_SCOPES,
    }
    if user_id is not None:
        kwargs["user_id"] = user_id
    return mint_test_token(**kwargs)


def second_user_token() -> str:
    return _mint_full_access_token(user_id=SECOND_TEST_USER)


@pytest.fixture(scope="session", autouse=True)
def _patch_pubkeys():
    """Install in-process JWKS so tokens minted with mint_test_token validate.

    The deployed app reads real JWKS from its config — this fixture is only
    needed when the FastAPI app runs in-process under TestClient.
    """
    monkeypatch_pubkeys()


@pytest.fixture(scope="session", autouse=True)
def _set_sdp_tmdata(monkeypatch_session):
    """Point SDP_SCRIPT_TMDATA at the in-repo fixture directory.

    The deployed chart sets this to a CAR URL.  We use the local file so
    component tests don't need network access.
    """
    monkeypatch_session.setenv("SDP_SCRIPT_TMDATA", _TMDATA_PATH)


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Session-scoped monkeypatch — pytest's built-in is function-scoped."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(autouse=True)
def _mock_ms_graph(monkeypatch):
    """Stub Microsoft Graph calls so PHT report/email paths don't hit Azure AD.

    The deployed chart configures a real client secret; the testcontainer
    setup has none, so we return canned values.  Tests that specifically
    exercise the MS Graph integration should override this.
    """
    monkeypatch.setattr(
        "ska_oso_services.pht.utils.ms_graph.get_pi_office_location",
        lambda *_, **__: "Unknown",
    )
    # report_processing imports the symbol directly, so patch it there too.
    monkeypatch.setattr(
        "ska_oso_services.pht.service.report_processing.get_pi_office_location",
        lambda *_, **__: "Unknown",
        raising=False,
    )


@pytest.fixture(scope="session")
def _app():
    """Session-scoped FastAPI app instance.

    A single app is reused across the session — DB isolation comes from the
    ``clean_db`` fixture in ``tests/db_fixtures.py`` truncating between tests.
    """
    return create_app(production=False)


@pytest.fixture
def client(_app, clean_db) -> TestClient:  # pylint: disable=unused-argument
    """Authenticated TestClient against the in-process app.

    Depends on ``clean_db`` (autouse via tests/db_fixtures.py) so each test
    starts from a known-empty DB.
    """
    token = _mint_full_access_token()
    return TestClient(_app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def temporary_different_user_client(_app):
    """Return a context-manager factory yielding a TestClient as SECOND_TEST_USER.

    Usage::

        def test_x(temporary_different_user_client):
            with temporary_different_user_client() as other_client:
                other_client.get(...)
    """

    @contextlib.contextmanager
    def _factory():
        token = second_user_token()
        yield TestClient(_app, headers={"Authorization": f"Bearer {token}"})

    return _factory


@pytest.fixture
def test_project(client) -> Project:
    prj_post_response = client.post(
        f"{ODT_BASE_API_URL}/prjs",
        headers={"Content-type": "application/json"},
    )
    return Project.model_validate_json(prj_post_response.content)


@pytest.fixture
def test_sbd(test_project, client) -> SBDefinition:
    ob_ref = test_project.obs_blocks[0].obs_block_id
    sbd = TestDataFactory.sbdefinition(sbd_id=None, ob_ref=ob_ref)
    sbd_post_response = client.post(
        f"{ODT_BASE_API_URL}/sbds",
        content=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    return SBDefinition.model_validate_json(sbd_post_response.content)


@pytest.fixture
def test_proposal(client) -> Proposal:
    post_response = client.post(
        f"{PHT_BASE_API_URL}/prsls/create",
        content=TestDataFactory.proposal().model_dump_json(),
        headers={"Content-type": "application/json"},
    )
    return Proposal.model_validate_json(post_response.content)


@pytest.fixture
def test_panel_id(client) -> str:
    response = client.post(
        f"{PHT_BASE_API_URL}/panels/create",
        content=TestDataFactory.panel_basic().model_dump_json(),
        headers={"Content-Type": "application/json"},
    )
    # API just returns the ID
    return response.json()


# See https://developer.skao.int/projects/ska-ser-xray/en/latest/guide/pytest.html
@pytest.hookimpl
def pytest_collection_modifyitems(
    session, config, items
):  # pylint: disable=unused-argument
    for item in items:
        for marker in item.iter_markers(name="xray"):
            test_key = marker.args[0]
            item.user_properties.append(("test_key", test_key))
