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

    invites: list[NewInvitation] = Field(min_length=1)


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
