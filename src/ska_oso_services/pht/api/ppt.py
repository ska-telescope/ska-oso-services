import logging

from fastapi import APIRouter
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import BadRequestError

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/proposal")


@router.post("/create", summary="Create a new proposal")
def create_proposal(proposal: Proposal) -> str:
    """
    Creates a new proposal in the ODA
    """
    LOGGER.debug("POST PROPOSAL create")

    try:
        with oda.uow() as uow:
            created_prsl = uow.prsls.add(proposal)
            uow.commit()
        LOGGER.info("Proposal successfully created with ID {created_prsl.prsl_id}")
        return created_prsl.prsl_id
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA")
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err
