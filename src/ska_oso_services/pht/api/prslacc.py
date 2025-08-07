import logging
from typing import Annotated

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import ProposalAccess

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_oso_services.common.error_handling import BadRequestError, NotFoundError
from ska_oso_services.pht.model import ProposalAccessResponse
from ska_oso_services.pht.utils.pht_handler import get_latest_entity_by_id

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/proposal-access", tags=["PPT API - Proposal Acess Management"]
)

@router.post(
    "/prslacl",
    summary="Creates a new Proposal Access"
)
def post_prslacl(prslacl: ProposalAccess, auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],) -> str:
    """
    Function that a POST /prslacl request is routed to.
    :param prslacl: The ProposalAccess object to be created.
    :param auth: The authentication context containing user information.
    :return: The access_id of the created ProposalAccess.
    """
    LOGGER.debug("Creating a new proposal access with data: %s", prslacl)
    try: 
        with oda.uow() as uow:
            persisted_prslacc = uow.prslacc.add(prslacl, auth.user_id)
            uow.commit()
        return persisted_prslacc.access_id
        
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err



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

