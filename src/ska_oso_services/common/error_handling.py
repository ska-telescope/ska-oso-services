import logging
import traceback
from functools import wraps
from http import HTTPStatus
from typing import Tuple, Union

from fastapi import JSONResponse, Request
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
                title="Not found",
                detail=f"Identifier {identifier} not found in repository",
            ),
        )
    else:
        LOGGER.exception(
            "KeyError raised by api function call, but not due to the "
            "sbd_id not being found in the ODA."
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=dict(
                title="Internal Server Error",
                detail=repr(err),
                traceback=ErrorResponseTraceback(
                    key="Internal Server Error",
                    type=str(type(err)),
                    full_traceback=traceback.format_exc(),
                ),
            ),
        )
