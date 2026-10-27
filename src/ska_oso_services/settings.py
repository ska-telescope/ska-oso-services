from typing import Annotated, Tuple

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_AUDIENCES = (
    # We default to "live" because in the case of a misconfiguration
    # we want to fail-safe to the most-restrictive setting.
    # Put another way: if someone goofs up, it's better if a dev
    # environment is accidentally accepting prod tokens than
    # vice versa
    "live:pht",
    "live:odt",
    # TODO: Remove this MS Entra once all clients are fully migrated to Indigo.
    "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b",
)

# Default expiry for S3 presigned URLs
PRESIGNED_URL_EXPIRY_TIME = 60


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
    )


class ODAConfig(ConfigBase):
    """Configuration for the Online Data Archive (ODA)."""

    host: str = Field(default="localhost", alias="PGHOST")
    port: int = Field(default=5432, alias="PGPORT")
    db: str = Field(default="oda", alias="PGDATABASE")
    user: str = Field(default="oda_admin", alias="PGUSER")
    password: str = Field(default="", alias="PGPASSWORD")


class AuthConfig(ConfigBase):
    """Configuration for Authentication and Authorization."""

    audience: Annotated[Tuple[str, ...], NoDecode] = Field(
        default=DEFAULT_AUDIENCES,
        alias="SKA_AUTH_AUDIENCE",
    )
    pipeline_tests_deployment: bool = Field(default=False, alias="PIPELINE_TESTS_DEPLOYMENT")

    @field_validator("audience", mode="before")
    def _parse_audience(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value


class S3Config(ConfigBase):
    """Configuration for S3 Object Storage."""

    access_key: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    secret_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    bucket: str = Field(alias="AWS_PHT_BUCKET_NAME")
    region: str = Field(alias="AWS_REGION")
    expiry: int = Field(default=PRESIGNED_URL_EXPIRY_TIME, alias="PRESIGNED_URL_EXPIRY_TIME")


class UserPortalConfig(ConfigBase):
    base_url: HttpUrl = Field(
        alias="USER_PORTAL_BASE_URL",
        description="The base URL for the SKAO User Portal in this environment.",
    )
    timeout: int = Field(
        default=10,
        alias="USER_PORTAL_TIMEOUT",
        description="How long to wait (in seconds) before User Portal requests time out",
    )
    token_url: HttpUrl = Field(
        alias="USER_PORTAL_TOKEN_URL",
        description="OAuth2 token endpoint for the User Portal client-credentials grant",
    )
    client_id: str = Field(
        min_length=1,
        alias="USER_PORTAL_CLIENT_ID",
        description="OAuth2 client ID for the User Portal client-credentials grant",
    )
    client_secret: SecretStr = Field(
        min_length=1,
        alias="USER_PORTAL_CLIENT_SECRET",
        description="OAuth2 client secret for the User Portal client-credentials grant",
    )
    token_scope: str = Field(
        min_length=1,
        alias="USER_PORTAL_TOKEN_SCOPE",
        description="Space-separated scopes to request in the client-credentials grant",
    )
    token_audience: str = Field(
        min_length=1,
        alias="USER_PORTAL_TOKEN_AUDIENCE",
        description="Audience to request in the client-credentials grant, e.g. test:portal",
    )


class GroupNamesConfig(ConfigBase):
    """
    How the access groups of proposals and panels are named. Proposals have three tiers
    (members, Co-Investigators with edit rights, PIs) and panels two (members, chairs).
    Each suffix is appended to the base group's name; a "/" in one makes a subgroup.
    """

    base: str = Field(
        default="app:pht:{skuid}",
        alias="PHT_GROUP_BASE",
        description="Name of a proposal's or panel's members group, with {skuid} for its ID",
    )
    coi_suffix: str = Field(
        default="/w",
        min_length=1,
        alias="PHT_GROUP_COI_SUFFIX",
        description="Suffix of a proposal's group for Co-Investigators with edit rights",
    )
    pi_suffix: str = Field(
        default="/w/a",
        min_length=1,
        alias="PHT_GROUP_PI_SUFFIX",
        description="Suffix of a proposal's group for its Principal Investigators",
    )
    chair_suffix: str = Field(
        default="/w/a",
        min_length=1,
        alias="PHT_GROUP_CHAIR_SUFFIX",
        description="Suffix of a panel's group for its chairs",
    )

    @field_validator("base")
    def _one_skuid_placeholder(cls, value: str) -> str:
        if value.count("{skuid}") != 1:
            raise ValueError("must contain {skuid} exactly once")
        return value

    @model_validator(mode="after")
    def _distinct_proposal_tiers(self) -> "GroupNamesConfig":
        if self.coi_suffix == self.pi_suffix:
            raise ValueError("The Co-Investigator and PI suffixes must differ")
        return self


class Settings(ConfigBase):
    """Centralized application settings."""

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    production: bool = Field(default=False, alias="PRODUCTION")
    api_path_prefix: str = Field(default="", alias="API_PATH_PREFIX")
    engineering_api_enabled: bool = Field(default=True, alias="ENGINEERING_API_ENABLED")
    sdp_script_tmdata: str | None = Field(default=None, alias="SDP_SCRIPT_TMDATA")

    # Sub-models
    oda: ODAConfig = Field(default_factory=ODAConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    s3: S3Config = Field(default_factory=S3Config)  # type: ignore
    userportal: UserPortalConfig = Field(default_factory=UserPortalConfig)  # type: ignore
    groups: GroupNamesConfig = Field(default_factory=GroupNamesConfig)


SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global SETTINGS  # noqa: PLW0603
    if SETTINGS is None:
        SETTINGS = Settings()
    return SETTINGS
