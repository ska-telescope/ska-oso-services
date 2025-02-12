"""
These functions map to the API paths, with the returned value being the API response
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from ska_oso_pdm import TelescopeType
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)

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

router = APIRouter(prefix="/prjs")


@router.get(
    "/{identifier}",
    summary="Get Project by identifier",
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
            if identifier not in uow.prjs:
                raise KeyError(
                    f"Not found. The requested prj_id {identifier} could not be found."
                )
            updated_prjs = uow.prjs.add(prj)
            uow.commit()

        return updated_prjs
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
        obs_block.sbd_ids.append(sbd.sbd_id)
        # Persist the change to the obs_block above
        uow.prjs.add(prj)
        uow.commit()

    return {"sbd": sbd, "prj": prj}
