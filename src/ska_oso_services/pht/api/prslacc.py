import logging

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import ProposalAccess

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.model import ProposalAccessResponse
from ska_oso_services.pht.utils.pht_handler import get_latest_entity_by_id

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/proposal-access", tags=["PPT API - Proposal Acess Management"]
)

@router.post(
    "/prslacl/{user_id}",
    summary="Create a new Proposal",
    description=(
        "The entity to be created in the request body should not contain a prsl_id as"
        " fetching this from SKUID is the responsibility of the ODA."
    ),
    response_model=ProposalAccess,
)
def post_prslacl(prslacl: ProposalAccess, user_id:str) -> ProposalAccess:
    """
    Function that a POST /prsls request is routed to.

    :param prsl: Proposal to persist from the request body
    :return: The Proposal as it exists in the ODA
    """

    with oda.uow() as uow:
        persisted_prsl = uow.prslacc.add(prslacl, "tonye")
        uow.commit()

    return persisted_prsl




@router.get("/{user_id}", summary="Get a list of proposals created by a user")
def get_access_for_user(user_id:str) -> list[ProposalAccessResponse]:
    # user_id = "test_user"
    with oda.uow() as uow:
        query_param = CustomQuery(user_id=user_id)
        proposal_access = get_latest_entity_by_id(
            uow.prslacc.query(query_param), "access_id"
        )
        if not proposal_access:
            return []
        return proposal_access
    


@router.put(
    "/{access_id}/{user_id}",
    summary="Update an existing proposal",
)
def update_access(access_id: str, access:ProposalAccess, user_id:str) -> ProposalAccess:

    with oda.uow() as uow:
        # Verify proposal exists
        existing = uow.prslacc.get(access_id)
        if not existing:
            LOGGER.info("Proposal not found for update: %s", access_id)
            raise NotFoundError(detail="Proposal not found: {access_id}")

        try:
            updated_prsl = uow.prslacc.add(access, user_id)  # Add is used for update
            uow.commit()
            LOGGER.info("Proposal %s updated successfully", access_id)
            return updated_prsl

        except ValueError as err:
            LOGGER.error("Validation failed for proposal %s: %s", access_id, err)
            raise BadRequestError(
                detail="Validation error while saving proposal: {err.args[0]}"
            ) from err

