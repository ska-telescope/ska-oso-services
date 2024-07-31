import logging
import traceback
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common.model import ErrorDetails, ErrorResponseTraceback

LOGGER = logging.getLogger(__name__)


def error_details(
    status: HTTPStatus,
    title: str,
    message: str,
    traceback: Optional[ErrorResponseTraceback],
):
    return ErrorDetails(
        status=status, title=title, message=message, traceback=traceback
    ).model_dump(mode="json", exclude_none=True)


class BadRequestError(HTTPException):
    """Custom class to ensure our errors are formatted consistently"""

    code = HTTPStatus.BAD_REQUEST

    def __init__(
        self,
        message: Optional[str] = None,
        title: Optional[str] = None,
        status_code: Optional[int] = None,
        traceback: Optional[ErrorResponseTraceback] = None,
    ):
        message = message or self.code.description
        title = title or self.code.phrase
        status_code = status_code or self.code
        detail = error_details(
            status=status_code,
            title=title,
            message=message,
            traceback=traceback,
        )
        super().__init__(status_code=status_code, detail=detail)


class UnprocessableEntityError(BadRequestError):
    code = HTTPStatus.UNPROCESSABLE_ENTITY


class NotFoundError(BadRequestError):
    code = HTTPStatus.NOT_FOUND


def _make_response(
    status: HTTPStatus, message: str, traceback: Optional[ErrorResponseTraceback] = None
) -> JSONResponse:
    """
    Utility helper to generate a JSONResponse to be returned by custom error handlers.
    """
    details = error_details(
        status, title=status.phrase, message=message, traceback=traceback
    )
    return JSONResponse(
        status_code=status,
        content={"detail": details},
    )


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
        # TODO make ODA exceptions more consistent:
        if identifier := request.path_params.get("identifier"):
            message = f"Identifier {identifier} not found in repository"
        else:
            message = err.args[0]
        return _make_response(HTTPStatus.NOT_FOUND, message=message)
    else:
        LOGGER.exception(
            "KeyError raised by api function call, but not due to the "
            "sbd_id not being found in the ODA."
        )
        return await dangerous_internal_server_handler(request, err)


async def dangerous_internal_server_handler(
    request: Request, err: Exception
) -> JSONResponse:
    """
    A custom handler function that returns a verbose HTTP 500 response containing
    detailed traceback information.

    This is a 'DANGEROUS' handler because it exposes internal implementation details to
    clients. Do not use in production systems!
    """
    return _make_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        message=repr(err),
        traceback=ErrorResponseTraceback(
            key=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            type=str(type(err)),
            full_traceback=traceback.format_exc(),
        ),
    )
