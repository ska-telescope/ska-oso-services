import logging
import traceback
from functools import wraps
from http import HTTPStatus
from typing import Callable, Tuple, Union

from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.common.model import (
    ErrorResponse,
    ErrorResponseTraceback,
    ValidationResponse,
)

Response = Tuple[Union[SBDefinition, ValidationResponse, ErrorResponse], int]

LOGGER = logging.getLogger(__name__)


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
                            f"Identifier {next(iter(kwargs.values()))} not "
                            "found in repository"
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


def error_response(err: Exception) -> Response:
    """
    Creates a general sever error response, with the error details formatted to help
    debugging.

    Before going live, we should remove the traceback and not expose the internals
    to the client, but for now it is useful for developers.

    :return: HTTP response server error
    """
    LOGGER.exception("Exception occurred while executing API function")
    response_body = ErrorResponse(
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail=repr(err),
        traceback=ErrorResponseTraceback(
            key="Internal Server Error",
            type=str(type(err)),
            full_traceback=traceback.format_exc(),
        ),
    )

    return response_body, HTTPStatus.INTERNAL_SERVER_ERROR
