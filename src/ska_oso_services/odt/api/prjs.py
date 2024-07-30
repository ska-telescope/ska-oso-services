"""
These functions map to the API paths, with the returned value being the API response
"""

import json
import logging
from http import HTTPStatus
from os import getenv

from fastapi import APIRouter, HTTPException
from ska_oso_pdm._shared import TelescopeType
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import Response, error_handler
from ska_oso_services.common.model import ErrorResponse

LOGGER = logging.getLogger(__name__)

ODA_BACKEND_TYPE = getenv("ODA_BACKEND_TYPE", "rest")

# For PI22, we are only supporting a single ObservingBlock in the
# Project, so hard code the id
OBS_BLOCK_ID = "ob-1"

router = APIRouter(prefix="/prjs", tags=["projects"])


@router.get("/{identifier}")
def prjs_get(identifier: str) -> Response:
    """
    Function that a GET /prjs/{identifier} request is routed to.

    Retrieves the Project with the given identifier from the
    underlying data store, if available

    :param identifier: identifier of the Project
    :return: a tuple of a Project (or ErrorResponse if not found) and an
        HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("GET PRJS prj_id: %s", identifier)
    breakpoint()
    with oda.uow as uow:
        return uow.prjs.get(identifier)


@router.post("/")
def prjs_post(body: Project) -> Response:
    """
    Function that a POST /prjs request is routed to.

    Validates then stores the Project in the underlying data store.

    The ODA is responsible for populating the sbd_id and metadata

    :param body: json request body as a dict
    :return: a tuple of a Porject as it exists in the ODA or error
        response and an HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("POST PRJ")

    prj = Project.model_validate_json(json.dumps(body))
    if not prj.obs_blocks:
        prj.obs_blocks = [ObservingBlock(obs_block_id=OBS_BLOCK_ID, sbd_ids=[])]
    if prj.author is None:
        prj.author = Author(pis=[], cois=[])

    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if prj.prj_id is not None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=(
                    "prj_id given in the body of the POST request. Identifier"
                    " generation for new entities is the responsibility of the ODA,"
                    " which will fetch them from SKUID, so they should not be given in"
                    " this request."
                ),
            ),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        with oda.uow as uow:
            updated_prj = uow.prjs.add(prj)
            uow.commit()
            # Unlike the other implementations, the RestRepository.add does
            # not return the entity with its metadata updated, as it is not
            # sent to the server until the commit.
            # So to display the metadata in the UI we need to do the extra fetch.
            if ODA_BACKEND_TYPE == "rest":
                updated_prj = uow.prjs.get(updated_prj.prj_id)
        return updated_prj
    except ValueError as err:
        LOGGER.exception("ValueError when adding Project to the ODA")
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            title="Validation Failed",
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


@router.get("/{identifier}")
def prjs_put(body: dict, identifier: str) -> Response:
    """
    Function that a PUT /prjs/{identifier} request is routed to.

    Validates then stores the Project with the given identifier
    in the underlying data store.

    :param body: json request body as a dict
    :param identifier: identifier of the Project
    :return: a tuple of an Project or error response and an HTTP status,
        which the Connexion will wrap in a response
    """
    LOGGER.debug("POST PRJS prj_id: %s", identifier)

    prj = Project.model_validate_json(json.dumps(body))

    if prj.prj_id != identifier:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            title="Unprocessable Entity, mismatched IDs",
            detail=(
                "There is a mismatch between the prj_id in the path for "
                "the endpoint and in the JSON payload"
            ),
        )
    try:
        with oda.uow as uow:
            if identifier not in uow.prjs:
                raise KeyError(
                    f"Not found. The requested prj_id {identifier} could not be found."
                )
            updated_prjs = uow.prjs.add(prj)
            uow.commit()
            # Unlike the other implementations, the RestRepository.add does
            # not return the entity with its metadata updated, as it is not
            # sent to the server until the commit.
            # So to display the metadata in the UI we need to do the extra fetch.
            if ODA_BACKEND_TYPE == "rest":
                updated_prjs = uow.prjs.get(updated_prjs.prj_id)

        return updated_prjs, HTTPStatus.OK
    except ValueError as err:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            title="Validation Failed",
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


@router.post("/{prj_id}/{obs_block_id}/sbd")
def prjs_sbds_post(prj_id: str, obs_block_id: str):
    """
    Function that a POST /prjs/{prj_id}/obs_block_id/sbd request is routed to.

    Creates an SBDefinition and links this in the Project.

    The returned response body is an object with the Project and SBDefinition
    as they exist in the ODA.

    :param prj_id: Identifier of the Project to create the SBDefinition in
    :param obs_block_id: The observing block within the Project the SBDefinition
        should be in
    :return: a tuple of an Project or error response and an HTTP status,
        which the Connexion will wrap in a response
    """
    with oda.uow as uow:
        prj = uow.prjs.get(prj_id)
        try:
            obs_block = next(
                obs_block
                for obs_block in prj.obs_blocks
                if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            return (
                ErrorResponse(
                    status=HTTPStatus.NOT_FOUND,
                    title="Not Found",
                    detail=f"Observing Block '{obs_block_id}' not found in Project",
                ),
                HTTPStatus.NOT_FOUND,
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

    return {"sbd": sbd, "prj": prj}, HTTPStatus.OK
