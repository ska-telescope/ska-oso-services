import logging

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
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


@router.get("/list/{user_id}", summary="Get a list of proposals created by a user")
def get_proposals_for_user(user_id: str) -> list[Proposal]:
    """
    Function that requests to GET /proposals/list are mapped to

    Retrieves the Proposals for the given user ID from the
    underlying data store, if available

    :param user_id: identifier of the Proposal
    :return: a tuple of a list of Proposal and a
        HTTP status, which the Connection will wrap in a response
    """

    LOGGER.debug("GET PROPOSAL LIST query for the user: {user_id}")
    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        proposals = uow.prsls.query(query_param)
    return proposals
