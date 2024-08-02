"""
These functions map to the API paths, with the returned value being the API response

Connexion maps the function name to the operationId in the OpenAPI document path
"""

import json
import logging
from http import HTTPStatus
from os import getenv

from fastapi import APIRouter, HTTPException
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common.error_handling import (
    BadRequestError,
    UnprocessableEntityError,
)
from ska_oso_services.common.model import ValidationResponse
from ska_oso_services.common.oda import oda
from ska_oso_services.odt.validation import validate_sbd

LOGGER = logging.getLogger(__name__)

ODA_BACKEND_TYPE = getenv("ODA_BACKEND_TYPE", "rest")

router = APIRouter(prefix="/sbds", tags=["SBDs"])


@router.get(
    "/create",
    summary="Create empty SBD",
    description=" Returns a json SchedulingBlockDefinition with empty or generated fields, to be populated and stored at a later point",
)
def sbds_create() -> SBDefinition:
    """
    Function that a GET /sbds/create request is routed to.

    Creates an 'empty' SBDefinition in the ODA, which just has default fields populated,
    and returns this to be populated and stored at a later point.

    The ODA handles the fetching of the ID from SKUID and the
    metadata when the SBDefinition is eventually stored.
    """
    # Create the empty SBD using defaults
    return SBDefinition()


@router.post(
    "/validate",
    summary="Validate an SBD",
    description="Validates the SchedulingBlockDefinition in the request body against the component definition (eg required fields, allowed ranges) and more complex business logic in the controller method.",
)
def sbds_validate(sbd: SBDefinition) -> ValidationResponse:
    """
    Function that a POST /sbds/validate request is routed to.

    Validates the SBDefinition in the request body against the
    component definition (eg required fields, allowed ranges) and more complex
    astronomy logic in the validation layer.

    :param sbd: PDM object SBDefinition
    :return: a ValidationResponse
    """
    validation_resp = validate(sbd)

    return validation_resp


@router.get(
    "/{identifier}",
    summary="Get SBD by identifier",
    description="Retrieves the SchedulingBlockDefinition with the given identifier from the underlying datas store, if available",
)
def sbds_get(identifier: str) -> SBDefinition:
    """
    Function that a GET /sbds/{identifier} request is routed to.

    Retrieves the SBDefinition with the given identifier from the
    underlying data store, if available

    :param identifier: identifier of the SBDefinition
    :return: a tuple of an SBDefinition (or ErrorResponse if not found) and a
        HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("GET SBD sbd_id: %s", identifier)
    with oda.uow as uow:
        sbd = uow.sbds.get(identifier)
    return sbd


@router.post(
    "/",
    summary="Create a new SBDefinition",
    description="Creates a new SchedulingBlockDefinition in the underlying data store. The response contains the entity as it exists in the data store, with an sbd_id and metadata populated.",
)
def sbds_post(sbd: SBDefinition) -> SBDefinition:
    """
    Function that a POST /sbds request is routed to.

    Validates then stores the SBDefinition in the underlying data store.

    The ODA is responsible for populating the sbd_id and metadata

    :param identifier: identifier of the SBDefinition
    :return: a tuple of an SBDefinition as it exists in the ODA or error
        response and a HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("POST SBD")
    validation_resp = validate(sbd)
    if not validation_resp.valid:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=validation_resp.model_dump(mode="json"),
        )

    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if sbd.sbd_id is not None:
        raise BadRequestError(
            title="Validation Failed",
            message=(
                "sbd_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of the ODA,"
                " which will fetch them from SKUID, so they should not be given in"
                " this request."
            ),
        )

    try:
        with oda.uow as uow:
            updated_sbd = uow.sbds.add(sbd)
            uow.commit()
            # Unlike the other implementations, the RestRepository.add does
            # not return the entity with its metadata updated, as it is not
            # sent to the server until the commit.
            # So to display the metadata in the UI we need to do the extra fetch.
            if ODA_BACKEND_TYPE == "rest":
                updated_sbd = uow.sbds.get(updated_sbd.sbd_id)
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        raise BadRequestError(
            title="Validation Failed",
            message=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        )
    else:
        return updated_sbd


@router.put(
    "/{identifier}",
    summary="Update an SBDefinition by identifier",
    description="Updates the SchedulingBlockDefinition with the given identifier in the underlying data store to create a new version.",
)
def sbds_put(sbd: SBDefinition, identifier: str) -> SBDefinition:
    """
    Function that a PUT /sbds/{identifier} request is routed to.

    Validates then stores the SBDefinition with the given identifier
    in the underlying data store.

    :param identifier: identifier of the SBDefinition
    :return: a tuple of an SBDefinition or error response and a HTTP status,
        which the Connexion will wrap in a response
    """
    LOGGER.debug("POST SBD sbd_id: %s", identifier)
    validation_resp = validate(sbd)
    if not validation_resp.valid:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=validation_resp.model_dump(mode="json"),
        )

    if sbd.sbd_id != identifier:
        raise UnprocessableEntityError(
            title="Unprocessable Entity, mismatched SBD IDs",
            message=(
                "There is a mismatch between the SBD ID for the endpoint and the "
                "JSON payload"
            ),
        )

    try:
        with oda.uow as uow:
            if identifier not in uow.sbds:
                raise KeyError(
                    f"Not found. The requested sbd_id {identifier} could not be found."
                )
            updated_sbd = uow.sbds.add(sbd)
            uow.commit()
            # Unlike the other implementations, the RestRepository.add does
            # not return the entity with its metadata updated, as it is not
            # sent to the server until the commit.
            # So to display the metadata in the UI we need to do the extra fetch.
            if ODA_BACKEND_TYPE == "rest":
                updated_sbd = uow.sbds.get(updated_sbd.sbd_id)
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        raise BadRequestError(
            title="Validation Failed",
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        )
    else:
        return updated_sbd


def validate(sbd: SBDefinition) -> ValidationResponse:
    """
    Validate SB Definition by running custom validation steps
    """
    validate_result = validate_sbd(sbd)

    valid = not bool(validate_result)

    return ValidationResponse(valid=valid, messages=validate_result)
