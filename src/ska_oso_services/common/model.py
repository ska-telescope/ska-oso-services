"""
TODO
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResponse:
    valid: bool
    messages: dict[str, str]


@dataclass
class ErrorResponseTraceback:
    key: str
    type: str
    full_traceback: str


@dataclass
class ErrorResponse:
    status: int
    title: str
    detail: str
    traceback: Optional[ErrorResponseTraceback] = None
