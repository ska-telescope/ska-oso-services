"""
These functions map to the API paths, with the returned value being the API response
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from ska_aaa_authhelpers import Role
from ska_oso_pdm import ProjectStatusHistory, TelescopeType
from ska_oso_pdm.entity_status_history import ProjectStatus
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.odt.api.sbds import _create_sbd_status_entity
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

API_ROLES = [Role.SW_ENGINEER, Role.LOW_TELESCOPE_OPERATOR, Role.MID_TELESCOPE_OPERATOR]

router = APIRouter(prefix="/prjs")


@router.get(
    "/{identifier}",
    summary="Get Project by identifier",
    dependencies=[
        Permissions(
            roles={API_ROLES}, scopes={Scope.ODT_READ, Scope.ODT_READWRITE}
        )
    ],
)
def prjs_get(identifier: str) -> Project:
    """
    Retrieves the Project with the given identifier from the underlying
    data store, if available
    """
    LOGGER.debug("GET PRJS prj_id: %s", identifier)
    with oda.uow() as uow:
        return uow.prjs.get(identifier)


@router.post(
    "/",
    summary="Create a new Project",
    dependencies=[Permissions(roles={API_ROLES}, scopes={Scope.ODT_READWRITE})],
)
def prjs_post(prj: Optional[Project] = None) -> Project:
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

    try:
        with oda.uow() as uow:
            updated_prj = uow.prjs.add(prj)

            prj_status = _create_prj_status_entity(updated_prj)
            uow.prjs_status_history.add(prj_status)

            uow.commit()
        return updated_prj
    except ValueError as err:
        LOGGER.exception("ValueError when adding Project to the ODA")
        raise BadRequestError(
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


@router.put(
    "/{identifier}",
    summary="Update a Project by identifier",
    dependencies=[Permissions(roles={API_ROLES}, scopes={Scope.ODT_READWRITE})],
)
def prjs_put(prj: Project, identifier: str) -> Project:
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
    try:
        with oda.uow() as uow:
            # This get will check if the identifier already exists
            # and throw an error if it doesn't
            uow.prjs.get(identifier)
            updated_prj = uow.prjs.add(prj)

            prj_status = _create_prj_status_entity(updated_prj)
            uow.prjs_status_history.add(prj_status)

            uow.commit()

        return updated_prj
    except ValueError as err:
        raise BadRequestError(
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


class PrjSBDLinkResponse(BaseModel):
    sbd: SBDefinition
    prj: Project


@router.post(
    "/{identifier}/{obs_block_id}/sbds",
    summary="Create a new SBDefinition linked to a project",
    dependencies=[Permissions(roles={API_ROLES}, scopes={Scope.ODT_READWRITE})],
)
def prjs_sbds_post(
    identifier: str, obs_block_id: str, sbd: Optional[SBDefinition] = None
) -> PrjSBDLinkResponse:
    """
    Creates an SBDefintiion linked to the given project.
    The response contains the entity as it exists in the data store,
    with an sbd_id and metadata populated.

    If no request body is passed, a default 'empty' SBDefinition will be created.
    """
    with oda.uow() as uow:
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
        sbd = uow.sbds.add(sbd_to_save)

        sbd_status = _create_sbd_status_entity(sbd)
        uow.sbds_status_history.add(sbd_status)

        obs_block.sbd_ids.append(sbd.sbd_id)
        # Persist the change to the obs_block above
        prj = uow.prjs.add(prj)

        prj_status = _create_prj_status_entity(prj)
        uow.prjs_status_history.add(prj_status)

        uow.commit()

    return {"sbd": sbd, "prj": prj}


@router.post(
    "/{identifier}/{obs_block_id}/generateSBDefinitions",
    summary="Generate SBDefinitions for an ObservingBlock within a Project",
    description="Generates SBDefinitions using the ScienceProgramme data in the "
    "ObservingBlock, persists those SBDefinitions in the ODA, adds a "
    "link to the SBDefinitions to the ObservingBlock then persists"
    "the updated Project/ObservingBlock",
    dependencies=[Permissions(roles={API_ROLES}, scopes={Scope.ODT_READWRITE})],
)
def prjs_ob_generate_sbds(identifier: str, obs_block_id: str) -> Project:
    LOGGER.debug(
        "POST PRJS generate SBDefinitions for prj_id: %s and obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    with oda.uow() as uow:
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
            updated_sbd = uow.sbds.add(sbd)

            sbd_status = _create_sbd_status_entity(updated_sbd)
            uow.sbds_status_history.add(sbd_status)

            obs_block.sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.add(prj)
        uow.commit()

    return updated_prj


@router.post(
    "/{identifier}/generateSBDefinitions",
    summary="Generate SBDefinitions for all ObservingBlocks within a Project",
    description="Generates SBDefinitions for each ObservingBlock in the Project, "
    "persists those SBDefinitions in the ODA, adds a link to the "
    "SBDefinitions to the ObservingBlock then persists the updated "
    "Project/ObservingBlock",
    dependencies=[Permissions(roles={API_ROLES}, scopes={Scope.ODT_READWRITE})],
)
def prjs_generate_sbds(identifier: str) -> Project:
    LOGGER.debug("POST PRJS generate SBDefinitions for prj_id: %s", identifier)
    with oda.uow() as uow:
        prj = uow.prjs.get(identifier)
        for obs_block in prj.obs_blocks:
            # Overwrite any existing SBDefinitions that were
            # linked to the ObservingBlock
            obs_block.sbd_ids = []

            sbds = generate_sbds(obs_block)

            for sbd in sbds:
                updated_sbd = uow.sbds.add(sbd)

                sbd_status = _create_sbd_status_entity(updated_sbd)
                uow.sbds_status_history.add(sbd_status)

                obs_block.sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.add(prj)
        uow.commit()

    return updated_prj


def _create_prj_status_entity(prj: Project) -> ProjectStatusHistory:
    return ProjectStatusHistory(
        prj_ref=prj.prj_id,
        prj_version=prj.metadata.version,
        # At the start of PI26, the status lifecycle isn't fully in place
        # We just set the default status to READY as this is required to be
        # executed in the OET UI
        current_status=ProjectStatus.READY,
        previous_status=ProjectStatus.READY,
    )
