"""
These functions map to the API paths, with the returned value being the API response

Connexion maps the function name to the operationId in the OpenAPI document path
"""

import json
import logging
from http import HTTPStatus
from os import getenv

from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services import oda
from ska_oso_services.common.error_handling import Response, error_handler
from ska_oso_services.common.model import ErrorResponse, ValidationResponse
from ska_oso_services.odt.validation import validate_sbd

LOGGER = logging.getLogger(__name__)

ODA_BACKEND_TYPE = getenv("ODA_BACKEND_TYPE", "rest")


@error_handler
def sbds_create() -> Response:
    """
    Function that a GET /sbds/create request is routed to.

    Creates an 'empty' SBDefinition in the ODA, which just has default fields populated,
    and returns this to be populated and stored at a later point.

    The ODA handles the fetching of the ID from SKUID and the
    metadata when the SBDefinition is eventually stored.

    :return: a tuple of an SBDefinition and a HTTP status,
        which the Connexion will wrap in a response
    """
    # Create the empty SBD using defaults
    sbd = SBDefinition()

    return sbd, HTTPStatus.OK


@error_handler
def sbds_validate(body: dict) -> Response:
    """
    Function that a POST /sbds/validate request is routed to.

    Validates the SBDefinition in the request body against the
    component definition (eg required fields, allowed ranges) and more complex
    astronomy logic in the validation layer.

    :param body: dict of an SBDefinition
    :return: a tuple of a ValidationResponse and a HTTP status,
        which the Connexion will wrap in a response
    """
    validation_resp = validate(body)

    return validation_resp, HTTPStatus.OK


@error_handler
def sbds_get(identifier: str) -> Response:
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
    return sbd, HTTPStatus.OK


@error_handler
def sbds_post(body: dict) -> Response:
    """
    Function that a POST /sbds request is routed to.

    Validates then stores the SBDefinition in the underlying data store.

    The ODA is responsible for populating the sbd_id and metadata

    :param identifier: identifier of the SBDefinition
    :return: a tuple of an SBDefinition as it exists in the ODA or error
        response and a HTTP status, which the Connexion will wrap in a response
    """
    LOGGER.debug("POST SBD")
    validation_resp = validate(body)
    if not validation_resp.valid:
        return (
            validation_resp,
            HTTPStatus.BAD_REQUEST,
        )

    sbd = OPENAPI_CODEC.loads(SBDefinition, json.dumps(body))

    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if sbd.sbd_id is not None:
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=(
                    "sbd_id given in the body of the POST request. Identifier"
                    " generation for new entities is the responsibility of the ODA,"
                    " which will fetch them from SKUID, so they should not be given in"
                    " this request."
                ),
            ),
            HTTPStatus.BAD_REQUEST,
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
        return (
            updated_sbd,
            HTTPStatus.OK,
        )
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
            ),
            HTTPStatus.BAD_REQUEST,
        )


@error_handler
def sbds_put(body: dict, identifier: str) -> Response:
    """
    Function that a PUT /sbds/{identifier} request is routed to.

    Validates then stores the SBDefinition with the given identifier
    in the underlying data store.

    :param identifier: identifier of the SBDefinition
    :return: a tuple of an SBDefinition or error response and a HTTP status,
        which the Connexion will wrap in a response
    """
    LOGGER.debug("POST SBD sbd_id: %s", identifier)
    validation_resp = validate(body)
    if not validation_resp.valid:
        return validation_resp, HTTPStatus.BAD_REQUEST

    sbd = OPENAPI_CODEC.loads(SBDefinition, json.dumps(body))
    if sbd.sbd_id != identifier:
        return (
            ErrorResponse(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity, mismatched SBD IDs",
                detail=(
                    "There is a mismatch between the SBD ID for the endpoint and the "
                    "JSON payload"
                ),
            ),
            HTTPStatus.UNPROCESSABLE_ENTITY,
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

        return updated_sbd, HTTPStatus.OK
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
            ),
            HTTPStatus.BAD_REQUEST,
        )


def validate(sbd: dict) -> ValidationResponse:
    """
    Validate SB Definition JSON. Validation includes checking that the SBD can be
    loaded using the PDM CODEC and passes custom validation steps
    """
    validate_result = validate_sbd(json.dumps(sbd))

    valid = not bool(validate_result)

    return ValidationResponse(valid, validate_result)
