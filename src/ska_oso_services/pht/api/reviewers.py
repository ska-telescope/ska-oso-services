from fastapi import APIRouter

from ska_oso_services.pht.utils.constants import REVIEWERS

router = APIRouter()


@router.post("/reviewers", summary="Retrieve a list of reviewers")
def get_reviewers() -> list[dict]:
    return REVIEWERS
