from enum import Enum
from os import getenv

import pytest
from requests import Session
from ska_aaa_authhelpers.roles import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

AUDIENCE = getenv("SKA_AUTH_AUDIENCE", "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b")

TENANT_ID = "78887040-bad7-494b-8760-88dcacfb3805"
CLIENT_ID = "e4d6bb9b-cdd0-46c4-b30a-d045091b501b"
CLIENT_SECRET = getenv("OSO_CLIENT_SECRET", "OSO_CLIENT_SECRET")
SCOPE = ["https://graph.microsoft.com/.default"]


class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"


@pytest.fixture(scope="session")
def authrequests():
    req = Session()
    token = mint_test_token(
        audience=AUDIENCE,
        roles=[
            Role.ANY,
            Role.OPS_PROPOSAL_ADMIN,
            Role.OPS_REVIEWER_SCIENCE,
            Role.OPS_REVIEWER_TECHNICAL,
            Role.SW_ENGINEER,
        ],
        scopes=[
            Scope.ODT_READWRITE,
            Scope.ODT_READ,
            Scope.PHT_READ,
            Scope.PHT_READWRITE,
        ],
    )
    req.headers.update({"Authorization": f"Bearer {token}"})
    return req


# See https://developer.skao.int/projects/ska-ser-xray/en/latest/guide/pytest.html
@pytest.hookimpl
def pytest_collection_modifyitems(session, config, items):  # pylint: disable=unused-argument
    for item in items:
        for marker in item.iter_markers(name="xray"):
            test_key = marker.args[0]
            item.user_properties.append(("test_key", test_key))
