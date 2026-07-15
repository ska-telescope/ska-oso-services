import os

TEST_BASE_API_URL = "/ska-oso-services/oso/api/v0"
ODT_BASE_API_URL = f"{TEST_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{TEST_BASE_API_URL}/pht"
FAKE_USER_PORTAL_PORT = 60517


def pytest_configure():
    # Set test defaults early so settings created during module imports use these values.
    os.environ.setdefault("API_PATH_PREFIX", TEST_BASE_API_URL)
    os.environ.setdefault("SKA_AUTH_AUDIENCE", "test:pht,test:odt")
    os.environ.setdefault("USER_PORTAL_BASE_URL", f"http://localhost:{FAKE_USER_PORTAL_PORT}")
    os.environ.setdefault("AWS_PHT_BUCKET_NAME", "test-bucket")
    os.environ.setdefault("AWS_REGION", "eu-west-2")
    os.environ.setdefault(
        "SDP_SCRIPT_TMDATA",
        f"file://{os.path.join(os.path.dirname(__file__), 'tmdata')}",
    )
