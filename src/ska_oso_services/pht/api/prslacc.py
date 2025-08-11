import logging
import uuid
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import ProposalAccess

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.pht.model import (
    ProposalAccessByProposalResponse,
    ProposalAccessCreate,
    ProposalAccessResponse,
)
from ska_oso_services.pht.utils.pht_handler import get_latest_entity_by_id

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/proposal-access", tags=["PPT API - Proposal Acess Management"]
)


@router.post("/prslacl", summary="Creates a new Proposal Access")
def post_prslacl(
    prslacl: ProposalAccessCreate,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> str:
    """
    This endpoint will be removed in the future, use the PUT endpoint instead.
    as there will be no creation of a new proposal access, only updates.
    """
    LOGGER.debug("Creating a new proposal access for user: %s", prslacl.user_id)
    try:
        rand_part = uuid.uuid4().hex[:6]
        prslacl.access_id = f"prslacc-{rand_part}-{prslacl.user_id[:7]}"
        with oda.uow() as uow:
            persisted_prslacc = uow.prslacc.add(prslacl, auth.user_id)
            uow.commit()
        return persisted_prslacc.access_id

    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err


@router.get(
    "/user", summary="Get a list of proposals the requesting user has access to"
)
def get_access_for_user(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> list[ProposalAccessResponse]:
    LOGGER.debug("Retrieving proposals for user: %s", auth.user_id)

    with oda.uow() as uow:
        query_param = CustomQuery(user_id=auth.user_id)
        proposal_access = get_latest_entity_by_id(
            uow.prslacc.query(query_param), "access_id"
        )
    if not proposal_access:
        return []
    return proposal_access


@router.get("/{prsl_id}", summary="Get a list of access of proposals ")
def get_access_by_prsl_id(
    prsl_id: str,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> list[ProposalAccessByProposalResponse]:
    LOGGER.debug("Retrieving proposals for user: %s", auth.user_id)

    with oda.uow() as uow:
        query_param = CustomQuery(prsl_id=prsl_id)
        proposal_access = get_latest_entity_by_id(
            uow.prslacc.query(query_param), "access_id"
        )
    if not proposal_access:
        return []
    print(proposal_access)
    return proposal_access


@router.put(
    "/user/{access_id}",
    summary="Update an existing proposal access",
)
def update_access(
    access_id: str,
    access: ProposalAccess,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> ProposalAccess:

    try:
        with oda.uow() as uow:
            updated_prsl = uow.prslacc.add(access, auth.user_id)
            uow.commit()
            LOGGER.info("Proposal access id %s updated successfully", access.access_id)
            return updated_prsl

    except ValueError as err:
        LOGGER.error("Validation failed for proposal %s: %s", access_id, err)
        raise BadRequestError(
            detail="Validation error while saving proposal: {err.args[0]}"
        ) from err
