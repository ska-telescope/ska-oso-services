from collections.abc import Iterable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from ska_aaa_authhelpers import AuthContext, Requires, Role
from ska_aaa_authhelpers.security import DEFAULT_ISSUERS, DEFAULT_PUBLIC_KEYS, KeysType
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS

from ska_oso_services.settings import get_settings

from .facts import PHT_ADMIN_GROUP, Facts
from .rules import PanelRules, ProposalRules, ReviewRules

DEFAULT_AUDIENCE = "live:pht"


class SecurityService:
    PHT_ADMIN_GROUP = PHT_ADMIN_GROUP

    def __init__(self, auth: AuthContext) -> None:
        self.auth = auth
        self.facts = Facts(auth)
        self.proposals = ProposalRules(self.facts)
        self.panels = PanelRules(self.facts)
        self.reviews = ReviewRules(self.facts)


def Security(
    *,
    roles: Iterable[Role | str],
    scopes: Iterable[str] = (),
    groups: Iterable[str] = (),
    app_ids: Iterable[str | UUID] = (),
    audience: str | Iterable[str] | None = None,
    keys: KeysType | None = None,
    issuer: str | Iterable[str] | None = None,
):
    configured_audience = audience if audience is not None else get_settings().auth.audience
    if not configured_audience:
        configured_audience = DEFAULT_AUDIENCE

    if get_settings().auth.pipeline_tests_deployment:
        effective_keys = keys if keys is not None else TEST_PUBLIC_KEYS
        effective_issuer = issuer if issuer is not None else TEST_ISSUER
    else:
        effective_keys = keys if keys is not None else DEFAULT_PUBLIC_KEYS
        effective_issuer = issuer if issuer is not None else DEFAULT_ISSUERS

    auth_dependency = Requires(
        roles=set(roles),
        scopes=set(scopes),
        groups=set(groups),
        app_ids=set(app_ids),
        audience=configured_audience,
        keys=effective_keys,
        issuer=effective_issuer,
    )

    def _dependency(auth: Annotated[AuthContext, auth_dependency]) -> SecurityService:
        return SecurityService(auth)

    return Depends(_dependency)
