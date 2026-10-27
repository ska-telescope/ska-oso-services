import os

import pytest

TEST_BASE_API_URL = "/ska-oso-services/oso/api/v0"
ODT_BASE_API_URL = f"{TEST_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{TEST_BASE_API_URL}/pht"
FAKE_USER_PORTAL_PORT = 60517
# Placeholder that tests/live uses to tell whether real User Portal credentials are set
FAKE_USER_PORTAL_CLIENT_SECRET = "test-secret"


def pytest_configure():
    # Set test defaults early so settings created during module imports use these values.
    os.environ.setdefault("API_PATH_PREFIX", TEST_BASE_API_URL)
    os.environ.setdefault("SKA_AUTH_AUDIENCE", "test:pht,test:odt")
    os.environ.setdefault("USER_PORTAL_BASE_URL", f"http://localhost:{FAKE_USER_PORTAL_PORT}")
    # Never used for a real grant: unit tests fake the token provider
    os.environ.setdefault("USER_PORTAL_TOKEN_URL", "http://localhost/token")
    os.environ.setdefault("USER_PORTAL_CLIENT_ID", "test-client")
    os.environ.setdefault("USER_PORTAL_CLIENT_SECRET", FAKE_USER_PORTAL_CLIENT_SECRET)
    os.environ.setdefault(
        "USER_PORTAL_TOKEN_SCOPE",
        "portal:users.read portal:groups.read portal:groups.write "
        "portal:invites.read portal:invites.write",
    )
    os.environ.setdefault("USER_PORTAL_TOKEN_AUDIENCE", "test:portal")
    os.environ.setdefault("AWS_PHT_BUCKET_NAME", "test-bucket")
    os.environ.setdefault("AWS_REGION", "eu-west-2")
    os.environ.setdefault(
        "SDP_SCRIPT_TMDATA",
        f"file://{os.path.join(os.path.dirname(__file__), 'tmdata')}",
    )


class FakeTokenProvider:
    """Stands in for the User Portal token cache so tests never call Indigo."""

    def __init__(self, token: str = "test-token") -> None:
        self.token = token
        self.invalidated = 0

    async def get_token(self) -> str:
        return self.token

    def invalidate(self) -> None:
        self.invalidated += 1


@pytest.fixture
def fake_user_portal_tokens(monkeypatch) -> FakeTokenProvider:
    # lazy import so that pytest_configure() can set env vars first
    from ska_oso_services.pht.service import user_portal

    tokens = FakeTokenProvider()
    monkeypatch.setattr(user_portal, "get_token_provider", lambda: tokens)
    return tokens
