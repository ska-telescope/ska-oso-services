from fastapi import APIRouter, HTTPException
from ska_aaa_authhelpers.roles import Role

from ska_oso_services.common.auth import Scope
from ska_oso_services.pht.service.security import Security, SecurityService

router = APIRouter(tags=["PMT API - Reviewers"])


@router.get(
    "/reviewers",
    summary="Retrieve a list of reviewers",
    dependencies=[
        Security(
            roles={Role.INTERNAL},
            scopes={Scope.PHT_READ},
            groups={SecurityService.PHT_ADMIN_GROUP},
        )
    ],
)
def get_reviewers() -> dict:
    """Returns a list of science and technical reviewers.

    Formerly returned a global list of user IDs:
        dict: {
            "sci_reviewers": list[dict],
            "tech_reviewers": list[dict]
        }
    """
    # FIXME: This needs to be rethought in coordination with SciOps
    # and some DB changes.
    # After speaking with Sarrvesh, the panels _are_ the reviewers.
    # There's no free-floating set of reviewers.
    # See:
    # https://skao.slack.com/archives/C0B85JLNVV3/p1785143279322739?thread_ts=1784891864.926169&cid=C0B85JLNVV3
    raise HTTPException(status_code=501, detail="Not Implemented")
