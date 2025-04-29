from enum import Enum
from functools import partial
from os import environ

from ska_aaa_authhelpers import Requires

AUDIENCE = environ.get("SKA_AUTH_AUDIENCE", "e4d6bb9b-cdd0-46c4-b30a-d045091b501b")

Permissions = partial(Requires, audience=AUDIENCE)


# Use StrEnum once we upgrade Python
class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
