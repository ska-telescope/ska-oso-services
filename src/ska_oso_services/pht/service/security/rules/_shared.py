from functools import wraps
from logging import getLogger
from typing import Any, Callable, Literal, NamedTuple, TypeAlias

from ska_aaa_authhelpers import AuthFailError
from ska_ser_skuid import EntityType, ShortSkuid

from ..facts import Facts

ProposalID: TypeAlias = ShortSkuid[Literal[EntityType.PRP]]
PanelID: TypeAlias = ShortSkuid[Literal[EntityType.PNL]]

log = getLogger("audit")


class RuleResult(NamedTuple):
    allowed: bool
    reason: str


class BaseRules:
    def __init__(self, facts: Facts) -> None:
        self.facts = facts


RuleFunction: TypeAlias = Callable[..., RuleResult]


def auth_rule(rule: RuleFunction) -> Callable[..., None]:
    @wraps(rule)
    def _wrapped(self: BaseRules, *args: Any, **kwargs: Any) -> None:
        result = rule(self, *args, **kwargs)
        msg = "{}: {}".format(("ALLOWED" if result.allowed else "FORBIDDEN"), result.reason)
        log.debug(msg, extra={"auth_ctx": self.facts.auth, "rule": rule.__name__})
        if not result.allowed:
            raise AuthFailError(result.reason)

    return _wrapped
