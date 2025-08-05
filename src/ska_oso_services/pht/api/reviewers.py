from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.utils.constants import REVIEWERS

router = APIRouter(tags=["PMT API - Reviewers"])


@router.get(
    "/reviewers",
    summary="Retrieve a list of reviewers",
    dependencies=[
        Permissions(
            roles=[Role.SW_ENGINEER, Role.OPS_PROPOSAL_ADMIN], scopes=[Scope.PHT_READ]
        )
    ],
)
def get_reviewers() -> list[dict]:
    """Returns a mocked list of reviewers

    Returns:
        list[dict]
    """
    # once aaa is implemented, this will be replaced with a call to the MS graph API
    return REVIEWERS
