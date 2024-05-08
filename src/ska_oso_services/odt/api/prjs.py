"""
These functions map to the API paths, with the returned value being the API response

Connexion maps the function name to the operationId in the OpenAPI document path
"""

import json
import logging
from http import HTTPStatus
from os import getenv

from ska_oso_pdm._shared import TelescopeType
from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services import oda
from ska_oso_services.common.error_handling import Response, error_handler
from ska_oso_services.common.model import ErrorResponse

LOGGER = logging.getLogger(__name__)

ODA_BACKEND_TYPE = getenv("ODA_BACKEND_TYPE", "rest")

# For PI22, we are only supporting a single ObservingBlock in the Project, so hard code the id
OBS_BLOCK_ID = "ob-1"


@error_handler
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
    with oda.uow as uow:
        prj = uow.prjs.get(identifier)
    return prj, HTTPStatus.OK


@error_handler
def prjs_post(body: dict) -> Response:
    """
    Function that a POST /prjs request is routed to.

    Validates then stores the Project in the underlying data store.

    The ODA is responsible for populating the sbd_id and metadata

    :param body: json request body as a dict
    :return: a tuple of a Porject as it exists in the ODA or error
        response and an HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("POST PRJ")

    prj = OPENAPI_CODEC.loads(Project, json.dumps(body))
    if prj.obs_blocks is None or len(prj.obs_blocks) == 0:
        prj.obs_blocks = [ObservingBlock(obs_block_id=OBS_BLOCK_ID, sbd_ids=[])]
    if prj.author is None:
        prj.author = Author(pis=[], cois=[])

    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if prj.prj_id is not None:
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
        return updated_prj, HTTPStatus.OK
    except ValueError as err:
        LOGGER.exception("ValueError when adding Project to the ODA")
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
            ),
            HTTPStatus.BAD_REQUEST,
        )


@error_handler
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

    prj = OPENAPI_CODEC.loads(Project, json.dumps(body))

    if prj.prj_id != identifier:
        return (
            ErrorResponse(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity, mismatched IDs",
                detail=(
                    "There is a mismatch between the prj_id in the path for "
                    "the endpoint and in the JSON payload"
                ),
            ),
            HTTPStatus.UNPROCESSABLE_ENTITY,
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
        LOGGER.exception("ValueError when adding Project to the ODA")
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
            ),
            HTTPStatus.BAD_REQUEST,
        )


@error_handler
def prjs_sbds_post(prj_id: str, obs_block_id: str):
    """ """
    # As of PI22, we only support a single observing block. Later, we will
    # support adding to different observing blocks with the relevant validation
    if obs_block_id != OBS_BLOCK_ID:
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=(
                    "Currently only a single Observing Block is supported, "
                    f"so obs_block_id must be '{OBS_BLOCK_ID}'."
                ),
            ),
            HTTPStatus.BAD_REQUEST,
        )

    with oda.uow as uow:
        prj = uow.prjs.get(prj_id)
        sbd = uow.sbds.add(
            SBDefinition(
                telescope=TelescopeType.SKA_MID,
                interface="https://schema.skao.int/ska-oso-pdm-sbd/0.1",
            )
        )
        if prj.obs_blocks is None or len(prj.obs_blocks) == 0:
            prj.obs_blocks = [ObservingBlock(name="ObservingBlock 1", sbd_ids=[])]

        prj.obs_blocks[0].sbd_ids.append(sbd.sbd_id)
        uow.prjs.add(prj)
        uow.commit()

    return sbd, HTTPStatus.OK
