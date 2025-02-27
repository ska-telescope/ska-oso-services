"""
These functions map to the API paths, with the returned value being the API response

Connexion maps the function name to the operationId in the OpenAPI document path
"""

import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    UnprocessableEntityError,
)
from ska_oso_services.common.model import ValidationResponse
from ska_oso_services.odt.validation import validate_sbd

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/sbds")


@router.get(
    "/create",
    summary="Create empty SBD",
)
def sbds_create() -> SBDefinition:
    """
    Returns a json SchedulingBlockDefinition with empty or generated fields,
    to be populated and stored at a later point
    """
    # Create the empty SBD using defaults
    return SBDefinition()


@router.post(
    "/validate",
    summary="Validate an SBD",
)
def sbds_validate(sbd: SBDefinition) -> ValidationResponse:
    """
    Validates the SchedulingBlockDefinition in the request body against the
    component definition (eg required fields, allowed ranges) and more
    complex business logic in the controller method.
    """
    validation_resp = validate(sbd)

    return validation_resp


@router.get("/{identifier}", summary="Get SBD by identifier")
def sbds_get(identifier: str) -> SBDefinition:
    """
    Retrieves the SchedulingBlockDefinition with the given identifier
    from the underlying data store, if available.
    """
    LOGGER.debug("GET SBD sbd_id: %s", identifier)
    with oda.uow() as uow:
        sbd = uow.sbds.get(identifier)
    return sbd


@router.post(
    "/",
    summary="Create a new SBDefinition",
)
def sbds_post(sbd: SBDefinition) -> SBDefinition:
    """
    Creates a new SchedulingBlockDefinition in the underlying data store.
    The response contains the entity as it exists in the data store, with an
    sbd_id and metadata populated.
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
            detail=(
                "sbd_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of the ODA,"
                " which will fetch them from SKUID, so they should not be given in"
                " this request."
            ),
        )

    try:
        with oda.uow() as uow:
            updated_sbd = uow.sbds.add(sbd)
            uow.commit()
        return updated_sbd
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        raise BadRequestError(
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


@router.put(
    "/{identifier}",
    summary="Update an SBDefinition by identifier",
)
def sbds_put(sbd: SBDefinition, identifier: str) -> SBDefinition:
    """
    Updates the SchedulingBlockDefinition with the given identifier
    in the underlying data store to create a new version.
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
            detail=(
                "There is a mismatch between the SBD ID for the endpoint and the "
                "JSON payload"
            ),
        )

    try:
        with oda.uow() as uow:
            # This get will check if the identifier already exists
            # and throw an error if it doesn't
            uow.sbds.get(identifier)
            updated_sbd = uow.sbds.add(sbd)
            uow.commit()
        return updated_sbd
    except ValueError as err:
        LOGGER.exception("ValueError when adding SBDefinition to the ODA")
        raise BadRequestError(
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err


def validate(sbd: SBDefinition) -> ValidationResponse:
    """
    Validate SB Definition by running custom validation steps
    """
    validate_result = validate_sbd(sbd)

    valid = not bool(validate_result)

    return ValidationResponse(valid=valid, messages=validate_result)
