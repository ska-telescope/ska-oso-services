from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    """Base class for application data models - as distinct from PDM objects"""

    model_config = ConfigDict(
        extra="forbid", validate_default=True, validate_assignment=True
    )


class ValidationResponse(AppModel):
    valid: bool
    messages: dict[str, str]


class ErrorResponseTraceback(AppModel):
    key: str
    type: str
    full_traceback: str


class ErrorResponse(AppModel):
    status: HTTPStatus
    title: str | None = None
    detail: str
    traceback: ErrorResponseTraceback | None = None

    def model_post_init(self, context: Any, /) -> None:
        if self.title is None:
            self.title = self.status.phrase
