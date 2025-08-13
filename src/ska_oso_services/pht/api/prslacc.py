import logging
import uuid
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import ProposalAccess, ProposalRole

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import BadRequestError, ForbiddenError
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


@router.post("/create", summary="Creates a new Proposal Access")
def post_create_access(
    prslacc_create: ProposalAccessCreate,
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
    LOGGER.debug("Creating a new proposal access")
    try:
        rand_part = uuid.uuid4().hex[:6]
        prslacc_create.access_id = f"prslacc-{rand_part}-{prslacc_create.user_id[:7]}"
        with oda.uow() as uow:
            persisted_prslacc = uow.prslacc.add(prslacc_create, auth.user_id)
            uow.commit()
        return persisted_prslacc.access_id

    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal access to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed attempting to create proposal access: '{err.args[0]}'",
        ) from err


@router.get(
    "/user", summary="Get a list of proposal access the requesting user has access to"
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
    LOGGER.debug("Retrieving proposal access for user: %s", auth.user_id)

    with oda.uow() as uow:
        query_param = CustomQuery(user_id=auth.user_id)
        proposal_access = get_latest_entity_by_id(
            uow.prslacc.query(query_param), "access_id"
        )
    if not proposal_access:
        return []
    return proposal_access


@router.get("/{prsl_id}", summary="Get a list of proposal access by prsl id")
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
    # pylint: disable=unused-argument
    LOGGER.debug("Retrieving proposal access for prsl id: %s", prsl_id)

    with oda.uow() as uow:
        query_param = CustomQuery(prsl_id=prsl_id)
        proposal_access = get_latest_entity_by_id(
            uow.prslacc.query(query_param), "access_id"
        )
    if not proposal_access:
        return []
    else:
        query_param_pi = CustomQuery(
            user_id=auth.user_id, role=ProposalRole.PrincipalInvestigator
        )
        proposal_access_pi = get_latest_entity_by_id(
            uow.prslacc.query(query_param_pi), "access_id"
        )

        if not proposal_access_pi:
            raise ForbiddenError(
                detail=(
                    "Forbidden error while getting proposal access: "
                    "Not Principal Investigator"
                )
            )

    return proposal_access


@router.put(
    "/user/{access_id}",
    summary="Update an existing proposal access by access id",
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
        LOGGER.error(
            "Validation failed for proposal access with id %s: %s", access_id, err
        )
        raise BadRequestError(
            detail="Validation error while saving proposal access: {err.args[0]}"
        ) from err
