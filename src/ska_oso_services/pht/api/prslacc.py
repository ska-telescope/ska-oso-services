import logging
from typing import Annotated

from fastapi import APIRouter, Response
from ska_aaa_authhelpers import Role
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm.proposal import ProposalAccess, ProposalRole
from ska_ser_skuid import EntityType, int_skuid, mint_skuid

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import BadRequestError, ForbiddenError
from ska_oso_services.pht.models.schemas import (
    ProposalAccessByProposalResponse,
    ProposalAccessCreate,
    ProposalAccessResponse,
)
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proposal-access", tags=["PPT API - Proposal Access Management"])


@router.post("/create", summary="Creates a new Proposal Access", deprecated=True)
def post_create_access(
    prslacc_create: ProposalAccessCreate,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    response: Response,
) -> str:
    """
    This endpoint will be removed in the future, use the PUT endpoint instead.
    as there will be no creation of a new proposal access, only updates.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</pht/prsls/{prsl_id}/invites>; rel="successor-version"'
    logger.debug("Creating a new proposal access")
    try:
        # proposal access table is a temp measure without a skuid
        # type. For now just hack this with a string replace, as
        # we just need a unique string
        prslacc_create.access_id = mint_skuid(EntityType.PRP).replace("prp", "acs")
        with oda.uow() as uow:
            persisted_prslacc = uow.prslacc.add(prslacc_create, security.auth.user_id)
            uow.commit()
        return persisted_prslacc.access_id

    except ValueError as err:
        logger.exception("ValueError when adding proposal access to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed attempting to create proposal access: '{err.args[0]}'",
        ) from err


@router.get(
    "/user",
    summary="Get a list of proposal access the requesting user has access to",
    deprecated=True,
)
def get_access_for_user(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    response: Response,
) -> list[ProposalAccessResponse]:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</pht/prsls/{prsl_id}/invites>; rel="successor-version"'
    logger.debug("Retrieving proposal access for user: %s", security.auth.user_id)

    with oda.uow() as uow:
        query_param = CustomQuery(user_id=security.auth.user_id)
        proposal_access = get_latest_entity_by_id(uow.prslacc.query(query_param), "access_id")
    if not proposal_access:
        return []
    return proposal_access


@router.get(
    "/{prsl_id}",
    summary="Get a list of proposal access by prsl id",
    deprecated=True,
)
def get_access_by_prsl_id(
    prsl_id: str,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    response: Response,
) -> list[ProposalAccessByProposalResponse]:
    # pylint: disable=unused-argument
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'</pht/prsls/{prsl_id}/invites>; rel="successor-version"'
    logger.debug("Retrieving proposal access for prsl id: %s", prsl_id)

    with oda.uow() as uow:
        query_param_pi = CustomQuery(
            prsl_fk=int_skuid(prsl_id).uid,
            user_id=security.auth.user_id,
            role=ProposalRole.PrincipalInvestigator,
        )
        proposal_access_pi = get_latest_entity_by_id(
            uow.prslacc.query(query_param_pi), "access_id"
        )

        if not proposal_access_pi:
            raise ForbiddenError(
                detail=(
                    "Forbidden error while getting proposal access: Not Principal Investigator"
                )
            )

        query_param = CustomQuery(prsl_fk=int_skuid(prsl_id).uid)
        proposal_access = get_latest_entity_by_id(uow.prslacc.query(query_param), "access_id")

    if not proposal_access:
        return []

    return proposal_access


@router.put(
    "/user/{access_id}",
    summary="Update an existing proposal access by access id",
    deprecated=True,
)
def update_access(
    access_id: str,
    access: ProposalAccess,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    response: Response,
) -> ProposalAccess:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</pht/prsls/{prsl_id}/invites>; rel="successor-version"'
    try:
        with oda.uow() as uow:
            updated_prsl = uow.prslacc.add(access, security.auth.user_id)
            uow.commit()
            logger.info("Proposal access id %s updated successfully", access.access_id)
            return updated_prsl

    except ValueError as err:
        logger.error("Validation failed for proposal access with id %s: %s", access_id, err)
        raise BadRequestError(
            detail="Validation error while saving proposal access: {err.args[0]}"
        ) from err
