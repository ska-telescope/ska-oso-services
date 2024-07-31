import logging
import traceback
from functools import wraps
from http import HTTPStatus
from typing import Tuple, Union

from fastapi import Request
from fastapi.responses import JSONResponse
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common.model import (
    ErrorResponse,
    ErrorResponseTraceback,
    ValidationResponse,
)

Response = Tuple[Union[SBDefinition, ValidationResponse, ErrorResponse], int]

LOGGER = logging.getLogger(__name__)


async def oda_not_found_handler(request: Request, err: KeyError) -> JSONResponse:
    """
    A custom handler function to deal with KeyError raised by the ODA and
    return the correct HTTP 404 response.
    """
    # TODO there is a risk that the KeyError is not from the
    #  ODA not being able to find the entity. After BTN-1502 the
    #  ODA should raise its own exceptions which we can catch here
    is_not_found_in_oda = any("not found" in str(arg).lower() for arg in err.args)
    if is_not_found_in_oda:
        identifier = request.path_params.get("identifier", "")
        return JSONResponse(
            status_code=HTTPStatus.NOT_FOUND,
            content=dict(
                status=f"{HTTPStatus.NOT_FOUND.value}: {HTTPStatus.NOT_FOUND.phrase}",
                title=HTTPStatus.NOT_FOUND.phrase,
                detail=f"Identifier {identifier} not found in repository",
                traceback=None,
            ),
        )
    else:
        LOGGER.exception(
            "KeyError raised by api function call, but not due to the "
            "sbd_id not being found in the ODA."
        )
        raise
        return await dangerous_internal_server_handler(request, err)


async def dangerous_internal_server_handler(request: Request, err: Exception) -> JSONResponse:
    """
    A custom handler function that returns a verbose HTTP 500 response containing
    detailed traceback information.

    This is a 'DANGEROUS' handler because it exposes internal implementation details to
    clients. Do not use in production systems!
    """
    return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=dict(
                status=f"{HTTPStatus.INTERNAL_SERVER_ERROR.value}: {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}",
                title=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                detail=repr(err),
                traceback=ErrorResponseTraceback(
                    key=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                    type=str(type(err)),
                    full_traceback=traceback.format_exc(),
                ),
            ),
        )
