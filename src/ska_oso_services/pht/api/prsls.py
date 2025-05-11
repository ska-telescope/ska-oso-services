import logging

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.api import validation

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/prsls")


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


@router.get("/{proposal_id}", summary="Retrieve an existing proposal")
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
    """

    LOGGER.debug("GET PROPOSAL LIST query for the user: {user_id}")

    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        proposals = uow.prsls.query(query_param)

        if proposals is None:
            LOGGER.info("No proposals found for user: {user_id}")
            return []

        LOGGER.debug("Found {len(proposals)} proposals for user {user_id}")
        return proposals


@router.put("/{proposal_id}", summary="Update an existing proposal")
def update_proposal(proposal_id: str, prsl: Proposal) -> Proposal:
    """
    Updates a proposal in the underlying data store.

    :param proposal_id: identifier of the Proposal in the URL
    :param prsl: Proposal object payload from the request body
    :return: the updated Proposal object
    """
    LOGGER.debug("PUT PROPOSAL - Attempting update for proposal_id: {proposal_id}")

    # Ensure ID match
    if prsl.prsl_id != proposal_id:
        LOGGER.warning(
            "Proposal ID mismatch: path ID={proposal_id}, body ID={prsl.prsl_id}"
        )
        raise UnprocessableEntityError(
            detail="Proposal ID in path and payload do not match."
        )

    with oda.uow() as uow:
        # Verify proposal exists
        existing = uow.prsls.get(proposal_id)
        if not existing:
            LOGGER.info("Proposal not found for update: {proposal_id}")
            raise NotFoundError(detail="Proposal not found: {proposal_id}")

        try:
            updated_prsl = uow.prsls.add(prsl)  # Add is used for update
            uow.commit()
            LOGGER.info("Proposal {proposal_id} updated successfully")
            return updated_prsl

        except ValueError as err:
            LOGGER.error("Validation failed for proposal {proposal_id}: {err}")
            raise BadRequestError(
                detail="Validation error while saving proposal: {err.args[0]}"
            ) from err


@router.post("/validate", summary="Validate a proposal")
def validate_proposal(prsl: Proposal) -> dict:
    """
    Validates a submitted proposal via POST.

    Returns:
        dict: {
            "result": bool,
            "validation_errors": list[str]
        }
    """
    LOGGER.debug("POST PROPOSAL validate")
    result = validation.validate_proposal(prsl)

    return result
