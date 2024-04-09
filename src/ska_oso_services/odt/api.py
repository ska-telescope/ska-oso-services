"""
These functions map to the API paths, with the returned value being the API response

Connexion maps the function name to the operationId in the OpenAPI document path
"""

import json
import logging
import traceback
from functools import wraps
from http import HTTPStatus
from os import getenv
from typing import Callable, Tuple, Union

from ska_oso_pdm.entities.common import sb_definition as pdm
from ska_oso_pdm.generated.models.sb_definition import SBDefinition
from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC

from ska_oso_services import oda
from ska_oso_services.odt.adapter import (
    generated_model_from_pdm,
    pdm_from_generated_model,
)
from ska_oso_services.odt.generated.models.error_response import ErrorResponse
from ska_oso_services.odt.generated.models.error_response_traceback import (
    ErrorResponseTraceback,
)
from ska_oso_services.odt.generated.models.validation_response import ValidationResponse
from ska_oso_services.odt.validation import validate_sbd

Response = Tuple[Union[SBDefinition, ValidationResponse, ErrorResponse], int]

LOGGER = logging.getLogger(__name__)

ODA_BACKEND_TYPE = getenv("ODA_BACKEND_TYPE", "rest")


def error_handler(api_fn: Callable[[str], Response]) -> Callable[[str], Response]:
    """
    A decorator function to catch general errors and wrap in the correct HTTP response,
    otherwise Flask just returns a generic error messgae which isn't very useful.

    :param api_fn: A function which an HTTP request is mapped
        to and returns an HTTP response
    """

    @wraps(api_fn)
    def wrapper(*args, **kwargs):
        try:
            return api_fn(*args, **kwargs)
        except KeyError as err:
            # TODO there is a risk that the KeyError is not from the
            #  ODA not being able to find the entity. After BTN-1502 the
            #  ODA should raise its own exceptions which we can catch here
            is_not_found_in_oda = any(
                "not found" in str(arg).lower() for arg in err.args
            )
            if is_not_found_in_oda:
                return (
                    ErrorResponse(
                        status=HTTPStatus.NOT_FOUND,
                        title="Not Found",
                        detail=(
                            "SBDefinition with identifier"
                            f" {next(iter(kwargs.values()))} not found in repository"
                        ),
                    ),
                    HTTPStatus.NOT_FOUND,
                )
            else:
                LOGGER.exception(
                    "KeyError raised by api function call, but not due to the "
                    "sbd_id not being found in the ODA."
                )
                return error_response(err)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Error caught by general error handler.")
            return error_response(err)

    return wrapper


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
    pdm_sbd = pdm.SBDefinition()

    model_sbd = generated_model_from_pdm(pdm_sbd)
    return model_sbd, HTTPStatus.OK


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
    return generated_model_from_pdm(sbd), HTTPStatus.OK


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
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=(
                    f"SBD validation failed: '{'; '.join(validation_resp.messages)}'"
                ),
            ),
            HTTPStatus.BAD_REQUEST,
        )

    model_sbd = OPENAPI_CODEC.loads(SBDefinition, json.dumps(body))

    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if model_sbd.sbd_id is not None:
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
        sbd: SBDefinition = pdm_from_generated_model(model_sbd)
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
            generated_model_from_pdm(updated_sbd),
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
        return (
            ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                title="Validation Failed",
                detail=(
                    f"SBD validation failed: '{'; '.join(validation_resp.messages)}'"
                ),
            ),
            HTTPStatus.BAD_REQUEST,
        )

    model_sbd = OPENAPI_CODEC.loads(SBDefinition, json.dumps(body))
    if model_sbd.sbd_id != identifier:
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
        sbd: SBDefinition = pdm_from_generated_model(model_sbd)
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

        return generated_model_from_pdm(updated_sbd), HTTPStatus.OK
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

    valid = not bool(validate_result["validation_errors"])

    return ValidationResponse(valid, validate_result["validation_errors"])


def error_response(err: Exception) -> Response:
    """
    Creates a general sever error response, without exposing internals to client

    :return: HTTP response server error
    """
    LOGGER.exception("Exception occurred while executing API function")
    response_body = ErrorResponse(
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail=str(err.args),
        traceback=ErrorResponseTraceback(
            key=err.args[0],
            type=str(type(err)),
            full_traceback=traceback.format_exc(),
        ),
    )

    return response_body, HTTPStatus.INTERNAL_SERVER_ERROR
