from typing import Annotated, Final, Tuple

from pydantic import Field, field_validator
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


class ODAConfig(BaseSettings):
    """Configuration for the Online Data Archive (ODA)."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    host: str | None = Field(default=None, alias="PGHOST")
    port: int = Field(default=5432, alias="PGPORT")
    db: str = Field(default="oda", alias="PGDATABASE")
    user: str = Field(default="oda_admin", alias="PGUSER")
    password: str | None = Field(default=None, alias="PGPASSWORD")


class AuthConfig(BaseSettings):
    """Configuration for Authentication and Authorization."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    audience: Annotated[Tuple[str, ...], NoDecode] = Field(
        default=DEFAULT_AUDIENCES,
        alias="SKA_AUTH_AUDIENCE",
    )
    pipeline_tests_deployment: bool = Field(default=False, alias="PIPELINE_TESTS_DEPLOYMENT")
    client_secret: str = Field(default="OSO_CLIENT_SECRET", alias="OSO_CLIENT_SECRET")

    @field_validator("audience", mode="before")
    def _parse_audience(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value


class EmailConfig(BaseSettings):
    """Configuration for the Email Service."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    user: str | None = Field(default=None, alias="PHT_EMAIL_USER")
    password: str | None = Field(default=None, alias="PHT_EMAIL_PASSWORD")


class S3Config(BaseSettings):
    """Configuration for S3 Object Storage."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    access_key: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    secret_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    bucket: str = Field(default="pht-bucket", alias="AWS_PHT_BUCKET_NAME")
    region: str = Field(default="us-west-2", alias="AWS_REGION")
    expiry: int = Field(default=PRESIGNED_URL_EXPIRY_TIME, alias="PRESIGNED_URL_EXPIRY_TIME")


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    production: bool = Field(default=False, alias="PRODUCTION")
    api_path_prefix: str = Field(default="", alias="API_PATH_PREFIX")
    engineering_api_enabled: bool = Field(default=True, alias="ENGINEERING_API_ENABLED")
    sdp_script_tmdata: str | None = Field(default=None, alias="SDP_SCRIPT_TMDATA")

    # Sub-models
    oda: ODAConfig = Field(default_factory=ODAConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    s3: S3Config = Field(default_factory=S3Config)


SETTINGS: Final[Settings] = Settings()


def get_settings() -> Settings:
    """Return the global frozen settings instance."""
    return SETTINGS
