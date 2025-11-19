"""
These functions map to the API paths, with the returned value being the API response
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from ska_aaa_authhelpers import AuthContext, Role
from ska_db_oda.persistence.fastapicontext import UnitOfWork
from ska_oso_pdm.entity_status_history import ProjectStatus, SBDStatus
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.odt.service.sbd_generator import generate_sbds

LOGGER = logging.getLogger(__name__)

DEFAULT_OBSERVING_BLOCK = ObservingBlock(
    obs_block_id="observing-block-12345", sbd_ids=[]
)

DEFAULT_AUTHOR = Author(pis=[], cois=[])

DEFAULT_PROJECT = Project(
    obs_blocks=[DEFAULT_OBSERVING_BLOCK.model_copy(deep=True)],
    author=DEFAULT_AUTHOR.model_copy(deep=True),
)

DEFAULT_SB_DEFINITION = SBDefinition(
    telescope=TelescopeType.SKA_MID,
    interface="https://schema.skao.int/ska-oso-pdm-sbd/0.1",
)

API_ROLES = {
    Role.SW_ENGINEER,
    Role.LOW_TELESCOPE_OPERATOR,
    Role.MID_TELESCOPE_OPERATOR,
    Role.OPERATIONS_SCIENTIST,
}

router = APIRouter(prefix="/prjs")


@router.get(
    "/{identifier}",
    summary="Get Project by identifier",
    dependencies=[
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READ, Scope.ODT_READWRITE})
    ],
)
def prjs_get(identifier: str, oda: UnitOfWork) -> Project:
    """
    Retrieves the Project with the given identifier from the underlying
    data store, if available
    """
    LOGGER.debug("GET PRJS prj_id: %s", identifier)
    with oda as uow:
        return uow.prjs.get(identifier)


@router.post("/", summary="Create a new Project")
def prjs_post(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    prj: Optional[Project] = None,
) -> Project:
    """
    Creates a new Project in the underlying data store. The response
    contains the entity as it exists in the data store, with
    a prj_id and metadata populated.
    """
    LOGGER.debug("POST PRJ")
    if prj is None:
        prj = DEFAULT_PROJECT.model_copy(deep=True)
    else:
        if not prj.obs_blocks:
            prj.obs_blocks = [DEFAULT_OBSERVING_BLOCK.model_copy(deep=True)]
        if prj.author is None:
            prj.author = DEFAULT_AUTHOR.model_copy(deep=True)
    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if prj.prj_id is not None:
        raise BadRequestError(
            detail=(
                "prj_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of the ODA,"
                " which will fetch them from SKUID, so they should not be given in"
                " this request."
            ),
        )

    with oda as uow:
        updated_prj = uow.prjs.add(prj, user=auth.user_id)
        # The status lifecycle isn't fully in place as of PI28, we set the default
        # status to READY as this is required to be executed in the OET UI
        uow.status.update_status(
            entity_id=updated_prj.prj_id,
            status=ProjectStatus.READY,
            updated_by=auth.user_id,
        )
        uow.commit()
    return updated_prj


@router.put("/{identifier}", summary="Update a Project by identifier")
def prjs_put(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    prj: Project,
    identifier: str,
    oda: UnitOfWork,
) -> Project:
    """
    Updates the Project with the given identifier in the underlying
    data store to create a new version.
    """
    LOGGER.debug("PUT PRJS prj_id: %s", identifier)

    if prj.prj_id != identifier:
        raise UnprocessableEntityError(
            detail=(
                "There is a mismatch between the prj_id in the path for "
                "the endpoint and in the JSON payload"
            ),
        )

    with oda as uow:
        # This get will check if the identifier already exists
        # and throw an error if it doesn't
        uow.prjs.get(identifier)
        updated_prj = uow.prjs.add(prj, user=auth.user_id)

        uow.commit()

    return updated_prj


class PrjSBDLinkResponse(BaseModel):
    sbd: SBDefinition
    prj: Project


@router.post(
    "/{identifier}/{obs_block_id}/sbds",
    summary="Create a new SBDefinition linked to a project",
)
def prjs_sbds_post(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
    sbd: Optional[SBDefinition] = None,
) -> PrjSBDLinkResponse:
    """
    Creates an SBDefintiion linked to the given project.
    The response contains the entity as it exists in the data store,
    with an sbd_id and metadata populated.

    If no request body is passed, a default 'empty' SBDefinition will be created.
    """
    with oda as uow:
        prj = uow.prjs.get(identifier)
        try:
            obs_block = next(
                obs_block
                for obs_block in prj.obs_blocks
                if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            # pylint: disable=raise-missing-from
            raise NotFoundError(
                detail=f"Observing Block '{obs_block_id}' not found in Project"
            )
        sbd_to_save = (
            sbd if sbd is not None else DEFAULT_SB_DEFINITION.model_copy(deep=True)
        )
        sbd = uow.sbds.add(sbd_to_save, user=auth.user_id)
        # The status lifecycle isn't fully in place as of PI28, we set the default
        # status to READY as this is required to be executed in the OET UI
        uow.status.update_status(
            entity_id=sbd.sbd_id,
            status=SBDStatus.READY,
            updated_by=auth.user_id,
        )

        obs_block.sbd_ids.append(sbd.sbd_id)
        # Persist the change to the obs_block above
        prj = uow.prjs.add(prj, user=auth.user_id)

        uow.commit()

    return {"sbd": sbd, "prj": prj}


@router.post(
    "/{identifier}/{obs_block_id}/generateSBDefinitions",
    summary="Generate SBDefinitions for an ObservingBlock within a Project",
    description="Generates SBDefinitions using the ScienceProgramme data in the "
    "ObservingBlock, persists those SBDefinitions in the ODA, adds a "
    "link to the SBDefinitions to the ObservingBlock then persists"
    "the updated Project/ObservingBlock",
)
def prjs_ob_generate_sbds(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
) -> Project:
    LOGGER.debug(
        "POST PRJS generate SBDefinitions for prj_id: %s and obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    with oda as uow:
        prj = uow.prjs.get(identifier)
        try:
            obs_block = next(
                obs_block
                for obs_block in prj.obs_blocks
                if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            # pylint: disable=raise-missing-from
            raise NotFoundError(
                detail=f"Observing Block '{obs_block_id}' not found in Project"
            )

        # Overwrite any existing SBDefinitions that were linked to the ObservingBlock
        obs_block.sbd_ids = []

        sbds = generate_sbds(obs_block)

        for sbd in sbds:
            updated_sbd = uow.sbds.add(sbd, user=auth.user_id)
            # The status lifecycle isn't fully in place as of PI28, we set the default
            # status to READY as this is required to be executed in the OET UI
            uow.status.update_status(
                entity_id=updated_sbd.sbd_id,
                status=SBDStatus.READY,
                updated_by=auth.user_id,
            )

            obs_block.sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.add(prj, user=auth.user_id)
        uow.commit()

    return updated_prj


@router.post(
    "/{identifier}/generateSBDefinitions",
    summary="Generate SBDefinitions for all ObservingBlocks within a Project",
    description="Generates SBDefinitions for each ObservingBlock in the Project, "
    "persists those SBDefinitions in the ODA, adds a link to the "
    "SBDefinitions to the ObservingBlock then persists the updated "
    "Project/ObservingBlock",
)
def prjs_generate_sbds(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
) -> Project:
    LOGGER.debug("POST PRJS generate SBDefinitions for prj_id: %s", identifier)
    with oda as uow:
        prj = uow.prjs.get(identifier)
        for obs_block in prj.obs_blocks:
            # Overwrite any existing SBDefinitions that were
            # linked to the ObservingBlock
            obs_block.sbd_ids = []

            sbds = generate_sbds(obs_block)

            for sbd in sbds:
                updated_sbd = uow.sbds.add(sbd, user=auth.user_id)
                # The status lifecycle isn't fully in place as of PI28, so we set the
                # default status to READY as required by OET UI for execution
                uow.status.update_status(
                    entity_id=updated_sbd.sbd_id,
                    status=SBDStatus.READY,
                    updated_by=auth.user_id,
                )

                obs_block.sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.add(prj, user=auth.user_id)
        uow.commit()

    return updated_prj
