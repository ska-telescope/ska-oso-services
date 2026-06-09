from enum import Enum
from functools import partial
from os import getenv

from ska_aaa_authhelpers import Requires
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS

DEFAULT_AUDIENCES = (
    # We default to "live" because in the case of a misconfiguration
    # we want to fail-safe to the most-restrictive setting.
    # Put another way: if someone goofs up, it's better if a dev
    # environment is accidentally accepting prod tokens than
    # vice versa
    "live:pht",
    "live:odt",
    # TODO: Remove this MS Entra once all clients are fully migrated to Indigo.
    "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b",
)
AUDIENCE = getenv("SKA_AUTH_AUDIENCE", DEFAULT_AUDIENCES)


# This should never be true in production, because
if getenv("PIPELINE_TESTS_DEPLOYMENT", "false") == "true":
    Permissions = partial(Requires, audience=AUDIENCE, keys=TEST_PUBLIC_KEYS, issuer=TEST_ISSUER)
else:
    Permissions = partial(Requires, audience=AUDIENCE)


# Use StrEnum once we upgrade Python
class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"
