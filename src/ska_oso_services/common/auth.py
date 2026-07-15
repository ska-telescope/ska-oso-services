from enum import Enum
from functools import partial

from ska_aaa_authhelpers import Requires
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS

from ska_oso_services.settings import get_settings

# This should never be true in production, because
if get_settings().auth.pipeline_tests_deployment:
    Permissions = partial(
        Requires,
        audience=get_settings().auth.audience,
        keys=TEST_PUBLIC_KEYS,
        issuer=TEST_ISSUER,
    )
else:
    Permissions = partial(Requires, audience=get_settings().auth.audience)


# Use StrEnum once we upgrade Python
class Scope(str, Enum):
    ODT_READ = "odt:read"
    ODT_READWRITE = "odt:readwrite"
    PHT_READ = "pht:read"
    PHT_READWRITE = "pht:readwrite"
    PHT_UPDATE = "pht:update"
