from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.pht.utils.ms_graph import get_users_by_group_id

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
def get_reviewers() -> list:
    """Returns a list of reviewers from MS Graph

    Returns:
        list[dict]
    """
    print("sci reviewer", Role.OPS_REVIEWER_SCIENCE)

    result = get_users_by_group_id(Role.OPS_REVIEWER_SCIENCE)

    return result
