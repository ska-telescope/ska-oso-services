"""Request and response models for the PHT invitation proxy API contract."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

# TODO: Review all the |None and UUID types in this module.
# user_id throughout is AuthContext.user_id (the Indigo userName / preferred_username
# claim), never null: the portal excludes accounts without one ("disabled") from its
# external API. The portal's own identifiers (portal_user_id, iam_user_id) are never exposed.


class NewInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The portal keys invites on email, whether or not the invitee already has an account
    email: EmailStr


class InviteCreateListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The portal's limit for one bulk request
    invites: list[NewInvitation] = Field(min_length=1, max_length=100)


class UserSearchItemResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(validation_alias="preferred_username")
    display_name: str
    email: str


class UserSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[UserSearchItemResponse]


class InviteCardResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invite_id: UUID
    group_name: str
    invited_email: str
    invited_by: str
    claim_state: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    expires_at: AwareDatetime
    responded_at: AwareDatetime | None = None


class InviteBulkItemResult(BaseModel):
    """The portal's outcome for one item of a bulk invite request."""

    model_config = ConfigDict(extra="ignore")

    index: int
    # created, duplicate, not_found or invalid
    status: str
    email: str | None = None
    detail: str | None = None
    invite: InviteCardResponse | None = None


class InviteBulkCreateResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[InviteBulkItemResult]


class InviteFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None
    # duplicate, not_found or invalid
    status: str
    detail: str | None


class InviteCreateListResponse(BaseModel):
    """
    The invites created, and the ones that weren't. Each is independent of the others,
    so a caller can retry only the failures.
    """

    model_config = ConfigDict(extra="forbid")

    invites: list[InviteCardResponse]
    failed: list[InviteFailure]


class InviteDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str


class InvitationsListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invites: list[InviteCardResponse]


class ProposalMember(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(validation_alias="preferred_username")
    display_name: str | None
    email: str | None = None
    affiliation: str | None = None
    has_write: bool = False
    is_admin: bool = False


class ProposalMembersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members: list[ProposalMember]
    # True if the portal answered from a cached copy of any of the proposal's groups
    stale: bool
