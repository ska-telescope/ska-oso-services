import logging

from fastapi import APIRouter
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import BadRequestError, NotFoundError

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/proposals")


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


@router.get("/{proposal_id}", summary="Get the existing proposal")
def get_proposal(proposal_id: str) -> Proposal:

    LOGGER.debug("GET PROPOSAL prsl_id: %s", proposal_id)

    try:
        with oda.uow() as uow:
            proposal = uow.prsls.get(proposal_id)
        LOGGER.info("Proposal retrieved successfully: %s", proposal_id)
        return proposal

    except KeyError as err:
        LOGGER.warning("Proposal not found: %s", proposal_id)
        raise NotFoundError(f"Could not find proposal: {proposal_id}") from err
