from enum import Enum
from functools import partial
from os import getenv

from ska_aaa_authhelpers import Requires
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS

AUDIENCE = getenv("SKA_AUTH_AUDIENCE", "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b")


# This should never be true in production, because
if getenv("PIPELINE_TESTS_DEPLOYMENT", "false") == "true":
    Permissions = partial(
        Requires, audience=AUDIENCE, keys=TEST_PUBLIC_KEYS, issuer=TEST_ISSUER
    )
else:
    Permissions = partial(Requires, audience=AUDIENCE)


# Use StrEnum once we upgrade Python
class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
