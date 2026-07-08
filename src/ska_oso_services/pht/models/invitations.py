"""Request and response models for the PHT invitation proxy API contract."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class InviteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    email: str | None = None

    @model_validator(mode="after")
    def xor_invite_type(self) -> Self:
        has_user_id = self.user_id is not None
        has_email = self.email is not None
        if has_user_id == has_email:
            raise ValueError("Exactly one of user_id or email must be provided")
        return self


class UserSearchItemResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: UUID | None = Field(validation_alias="portal_user_id")
    display_name: str
    email: str
    status: str | None = None
    has_iam_account: bool


class UserSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[UserSearchItemResponse]


class InviteCardResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # Fixme: We don't want to expose all of this to callers...
    invite_id: UUID
    group_name: str
    invited_email: str
    invited_by: str
    status: str
    claim_state: str
    accepted_via: str | None = None
    email_mismatch: bool
    claimed_by_user_id: UUID | None = Field(validation_alias="claimed_by_portal_user_id")
    created_at: str
    updated_at: str
    expires_at: str
    responded_at: str | None = None


class InviteListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[InviteCardResponse]
    next_cursor: str | None = None


class InviteDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
