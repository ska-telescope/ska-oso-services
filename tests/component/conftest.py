from os import getenv

import pytest
from requests import Session
from ska_aaa_authhelpers.test_helpers import mint_test_token

AUDIENCE = getenv("SKA_AUTH_AUDIENCE", "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b")


@pytest.fixture(scope="session")
def authrequests():
    req = Session()
    token = mint_test_token(audience=AUDIENCE, scopes={"odt:readwrite"})
    req.headers.update({"Authorization": f"Bearer {token}"})
    return req


# See https://developer.skao.int/projects/ska-ser-xray/en/latest/guide/pytest.html
@pytest.hookimpl
def pytest_collection_modifyitems(
    session, config, items
):  # pylint: disable=unused-argument
    for item in items:
        for marker in item.iter_markers(name="xray"):
            test_key = marker.args[0]
            item.user_properties.append(("test_key", test_key))
