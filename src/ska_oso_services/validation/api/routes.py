from typing import Any

from fastapi import APIRouter
from ska_oso_pdm import SBDefinition

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.model import AppModel
from ska_oso_services.odt.api.sbds import API_ROLES
from ska_oso_services.validation.model import ValidationIssue
from ska_oso_services.validation.sbdefinition import validate_sbdefinition

router = APIRouter(prefix="/validation", tags=["OSO Validation API endpoints"])


class ValidationResponse(AppModel):
    valid: bool | None = None
    messages: list[ValidationIssue]

    def model_post_init(self, context: Any, /) -> None:
        if self.valid is None:
            self.valid = not bool(self.messages)


@router.post(
    path="/sbd",
    summary="Validate an SBD TODO",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE})],
)
def validate_sbd(sbd: SBDefinition) -> ValidationResponse:
    result = validate_sbdefinition(sbd)

    return ValidationResponse(messages=result)
