from fastapi import APIRouter

from ska_oso_services.pht.utils.constants import REVIEWERS

router = APIRouter(tags=["PMT API - Reviewers"])


@router.get("/reviewers", summary="Retrieve a list of reviewers")
def get_reviewers() -> list[dict]:
    """Returns a mocked list of reviewers

    Returns:
        list[dict]
    """
    # once aaa is implemented, this will be replaced with a call to the MS graph API
    return REVIEWERS
