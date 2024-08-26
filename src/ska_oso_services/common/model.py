from typing import Optional

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


class ErrorDetails(AppModel):
    status: int
    title: str
    detail: str
    traceback: Optional[ErrorResponseTraceback] = None
