from typing import Any

from fastapi import APIRouter
from ska_oso_pdm import SBDefinition

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.model import AppModel
from ska_oso_services.odt.api.sbds import API_ROLES
from ska_oso_services.validation.model import ValidationContext, ValidationIssue
from ska_oso_services.validation.sbdefinition import validate_sbdefinition

router = APIRouter(prefix="/validate", tags=["OSO Validation API endpoints"])


class ValidationResponse(AppModel):
    valid: bool | None = None
    issues: list[ValidationIssue]

    def model_post_init(self, context: Any, /) -> None:
        if self.valid is None:
            self.valid = not bool(self.issues)


@router.post(
    path="/sbd",
    summary="Validates an SBDefinition returning any validation issues tied to"
    "specific parts of the SBDefinition as a JSONPath",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READ})],
)
def validate_sbd(sbd: SBDefinition) -> ValidationResponse:
    sbd_validation_context = ValidationContext(primary_entity=sbd, telescope=sbd.telescope)
    result = validate_sbdefinition(sbd_validation_context)

    return ValidationResponse(issues=result)
