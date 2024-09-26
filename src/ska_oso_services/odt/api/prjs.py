"""
These functions map to the API paths, with the returned value being the API response
"""

import logging

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

# For PI22, we are only supporting a single ObservingBlock in the
# Project, so hard code the id
OBS_BLOCK_ID = "ob-1"

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
    with oda as uow:
        return uow.prjs.get(identifier)


@router.post(
    "/",
    summary="Create a new Project",
)
def prjs_post(prj: Project) -> Project:
    """
    Creates a new Project in the underlying data store. The response
    contains the entity as it exists in the data store, with
    a prj_id and metadata populated.
    """
    LOGGER.debug("POST PRJ")

    if not prj.obs_blocks:
        prj.obs_blocks = [ObservingBlock(obs_block_id=OBS_BLOCK_ID, sbd_ids=[])]
    if prj.author is None:
        prj.author = Author(pis=[], cois=[])

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
        with oda as uow:
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
        with oda as uow:
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
    "/{prj_id}/{obs_block_id}/sbds",
    summary="Create a new, empty SBDefinition linked to a project",
)
def prjs_sbds_post(prj_id: str, obs_block_id: str) -> PrjSBDLinkResponse:
    """
    Creates an empty SBDefintiion linked to the given project.
    The response contains the entity as it exists in the data store,
    with an sbd_id and metadata populated.
    """
    with oda as uow:
        prj = uow.prjs.get(prj_id)
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

        sbd = uow.sbds.add(
            SBDefinition(
                telescope=TelescopeType.SKA_MID,
                interface="https://schema.skao.int/ska-oso-pdm-sbd/0.1",
            )
        )
        obs_block.sbd_ids.append(sbd.sbd_id)
        # Persist the change to the obs_block above
        uow.prjs.add(prj)
        uow.commit()

    return {"sbd": sbd, "prj": prj}
