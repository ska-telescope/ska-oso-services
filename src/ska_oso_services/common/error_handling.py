import logging
from http import HTTPStatus
from traceback import format_exc
from typing import List, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from ska_db_oda.persistence.domain.errors import (
    ODAError,
    ODANotFound,
    UniqueConstraintViolation,
)
from ska_ost_osd.common.error_handling import generic_exception_handler

from ska_oso_services.common.model import ErrorDetails, ErrorResponseTraceback

LOGGER = logging.getLogger(__name__)


def error_details(
    status: HTTPStatus,
    title: str,
    detail: str,
    traceback: Optional[ErrorResponseTraceback],
):
    return ErrorDetails(
        status=status, title=title, detail=detail, traceback=traceback
    ).model_dump(mode="json", exclude_none=True)


class OSDError(Exception):
    """Exception class for OSD errors."""

    def __init__(self, errors: List[dict]):
        self.errors = errors
        super().__init__(errors)


class BadRequestError(HTTPException):
    """Custom class to ensure our errors are formatted consistently"""

    code = HTTPStatus.BAD_REQUEST

    def __init__(
        self,
        detail: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        status_code = status_code or self.code
        detail = detail or self.code.description

        super().__init__(status_code=status_code, detail=detail)


class DuplicateError(BadRequestError):
    code = HTTPStatus.CONFLICT


class UnprocessableEntityError(BadRequestError):
    code = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, detail: Optional[str] = None):
        super().__init__(detail=detail)


class ForbiddenError(BadRequestError):
    code = HTTPStatus.FORBIDDEN

    def __init__(self, detail: Optional[str] = None):
        super().__init__(detail=detail)


class NotFoundError(BadRequestError):
    code = HTTPStatus.NOT_FOUND

    def __init__(self, detail: Optional[str] = None):
        super().__init__(detail=detail)


def _make_response(
    status: HTTPStatus, detail: str, traceback: Optional[ErrorResponseTraceback] = None
) -> JSONResponse:
    """
    Utility helper to generate a JSONResponse to be returned by custom error handlers.
    """
    details = error_details(
        status, title=status.phrase, detail=detail, traceback=traceback
    )
    return JSONResponse(
        status_code=status,
        content={"detail": details},
    )


async def oda_not_found_handler(request: Request, err: ODANotFound) -> JSONResponse:
    """
    A custom handler function to deal with NotFoundInODA raised by the ODA and
    return the correct HTTP 404 response.
    """
    LOGGER.debug("NotFoundInODA for path parameters %s", request.path_params)
    return JSONResponse(
        status_code=HTTPStatus.NOT_FOUND, content={"detail": err.message}
    )


async def oda_error_handler(_: Request, err: ODAError) -> JSONResponse:
    """
    A custom handler function to deal with general ODAError and
    return the correct 500 response.
    """
    LOGGER.error("ODAError with message %s", err.message)
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, content={"detail": err.message}
    )


async def oda_unique_constraint_handler(
    request: Request, err: UniqueConstraintViolation
) -> JSONResponse:
    """
    A custom handler function to deal with UniqueConstraintViolation raised by the ODA
    and return the correct HTTP 400 response.
    """
    LOGGER.debug(
        "UniqueConstraintViolation for path parameters %s", request.path_params
    )
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST, content={"detail": err.args[0]}
    )


async def dangerous_internal_server_handler(_: Request, err: Exception) -> JSONResponse:
    """
    A custom handler function that returns a verbose HTTP 500 response containing
    detailed traceback information.

    This is a 'DANGEROUS' handler because it exposes internal implementation details to
    clients. Do not use in production systems!
    """
    return _make_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        detail=repr(err),
        traceback=ErrorResponseTraceback(
            key=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            type=str(type(err)),
            full_traceback=format_exc(),
        ),
    )


async def osd_error_handler(request: Request, exc: OSDError):
    """
    Exception handler for OSDError that wraps the error
    as a ValueError and delegates handling to the generic_exception_handler.

    This function is designed to catch OSDError exceptions raised by the
    get_osd method and pass them to generic_exception_handler as a ValueError.
    """
    response = await generic_exception_handler(request, ValueError(exc.errors))
    return response
